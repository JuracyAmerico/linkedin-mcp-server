"""
LinkedIn profile analytics tools.

Scrapes the authenticated user's profile views page to extract
who has viewed their profile recently — useful for job search intelligence.
"""

import logging
from typing import Any

from fastmcp import Context, FastMCP

from linkedin_mcp_server.constants import TOOL_TIMEOUT_SECONDS
from linkedin_mcp_server.core.exceptions import AuthenticationError
from linkedin_mcp_server.dependencies import get_ready_extractor, handle_auth_error
from linkedin_mcp_server.error_handler import raise_tool_error

logger = logging.getLogger(__name__)


def register_analytics_tools(mcp: FastMCP) -> None:
    """Register all analytics-related tools with the MCP server."""

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        title="Get Profile Views",
        annotations={"readOnlyHint": True, "openWorldHint": False},
        tags={"analytics", "profile"},
        exclude_args=["extractor"],
    )
    async def get_profile_views(
        ctx: Context,
        extractor: Any | None = None,
    ) -> dict[str, Any]:
        """
        Get a list of people who recently viewed your LinkedIn profile.

        This requires an authenticated LinkedIn session (the logged-in user's
        own analytics). Returns raw text from the profile views page which
        the LLM should parse to extract viewer names, titles, companies,
        and approximate view dates.

        Note: LinkedIn may limit visibility based on account type (free vs Premium).
        Free accounts typically see the last 5 viewers; Premium sees all.

        Returns:
            Dict with url, sections (profile_views -> raw text), and optional references.
            The LLM should parse the raw text to extract individual viewers.
        """
        try:
            extractor = extractor or await get_ready_extractor(
                ctx, tool_name="get_profile_views"
            )
            url = "https://www.linkedin.com/analytics/profile-views/"

            logger.info("Scraping profile views analytics page")

            await ctx.report_progress(
                progress=0, total=100, message="Navigating to profile views"
            )

            extracted = await extractor.extract_page(
                url, section_name="profile_views"
            )

            await ctx.report_progress(progress=100, total=100, message="Complete")

            sections: dict[str, str] = {}
            references: dict[str, Any] = {}

            if extracted.text:
                sections["profile_views"] = extracted.text
                if extracted.references:
                    references["profile_views"] = extracted.references

            result: dict[str, Any] = {
                "url": url,
                "sections": sections,
            }
            if references:
                result["references"] = references
            return result

        except AuthenticationError as e:
            try:
                await handle_auth_error(e, ctx)
            except Exception as relogin_exc:
                raise_tool_error(relogin_exc, "get_profile_views")
        except Exception as e:
            raise_tool_error(e, "get_profile_views")  # NoReturn
