"""
LinkedIn group tools.

Scrapes posts from LinkedIn groups using the authenticated session.
Useful for extracting Q&A content, advice, and discussions from
professional communities.
"""

import logging
from typing import Any

from fastmcp import Context, FastMCP

from linkedin_mcp_server.constants import TOOL_TIMEOUT_SECONDS
from linkedin_mcp_server.core.exceptions import AuthenticationError
from linkedin_mcp_server.dependencies import get_ready_extractor, handle_auth_error
from linkedin_mcp_server.error_handler import raise_tool_error

logger = logging.getLogger(__name__)


def register_group_tools(mcp: FastMCP) -> None:
    """Register all group-related tools with the MCP server."""

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        title="Get Group Posts",
        annotations={"readOnlyHint": True, "openWorldHint": False},
        tags={"groups", "content"},
        exclude_args=["extractor"],
    )
    async def get_group_posts(
        ctx: Context,
        group_id: str,
        max_scrolls: int = 15,
        extractor: Any | None = None,
    ) -> dict[str, Any]:
        """
        Get recent posts from a LinkedIn group.

        Navigates to the group's feed page, scrolls to load posts, and
        extracts the visible content. LinkedIn groups require membership
        to view posts — the authenticated session must be a member.

        Args:
            group_id: The numeric LinkedIn group ID (from the group URL).
                      Example: "4930157" for Steve Dalton's 2HJS group.
            max_scrolls: Number of scroll iterations to load more posts
                         (default 15, each loads ~3-5 posts). Use higher
                         values for deeper historical reads.

        Returns:
            Dict with url, sections (group_posts -> raw text), and optional references.
            The LLM should parse the raw text to extract individual posts,
            authors, dates, and discussion threads.
        """
        try:
            extractor = extractor or await get_ready_extractor(
                ctx, tool_name="get_group_posts"
            )
            url = f"https://www.linkedin.com/groups/{group_id}/"

            logger.info("Scraping group %s with %d scroll iterations", group_id, max_scrolls)

            await ctx.report_progress(
                progress=0, total=100, message="Navigating to group feed"
            )

            # Navigate to the group page
            await extractor._navigate_to_page(url)

            # Check for auth barrier (group membership required)
            from linkedin_mcp_server.core.utils import (
                detect_rate_limit,
                handle_modal_close,
                scroll_to_bottom,
            )

            await detect_rate_limit(extractor._page)

            # Wait for main content
            from patchright.async_api import TimeoutError as PlaywrightTimeoutError

            try:
                await extractor._page.wait_for_selector("main", timeout=10000)
            except PlaywrightTimeoutError:
                logger.debug("No <main> element found on group page %s", url)

            await handle_modal_close(extractor._page)

            await ctx.report_progress(
                progress=20, total=100, message="Scrolling to load posts"
            )

            # Scroll aggressively to load lazy-loaded posts
            await scroll_to_bottom(
                extractor._page, pause_time=1.5, max_scrolls=max_scrolls
            )

            await ctx.report_progress(
                progress=80, total=100, message="Extracting content"
            )

            # Extract the full page content
            raw_result = await extractor._extract_root_content(["main"])
            raw = raw_result["text"]

            await ctx.report_progress(progress=100, total=100, message="Complete")

            sections: dict[str, str] = {}
            references: dict[str, Any] = {}

            if raw:
                # Strip LinkedIn noise (footer, sidebar)
                from linkedin_mcp_server.scraping.extractor import strip_linkedin_noise

                cleaned = strip_linkedin_noise(raw)
                if cleaned:
                    sections["group_posts"] = cleaned
                    if raw_result.get("references"):
                        from linkedin_mcp_server.scraping.link_metadata import (
                            build_references,
                        )

                        references["group_posts"] = build_references(
                            raw_result["references"], "group_posts"
                        )

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
                raise_tool_error(relogin_exc, "get_group_posts")
        except Exception as e:
            raise_tool_error(e, "get_group_posts")  # NoReturn
