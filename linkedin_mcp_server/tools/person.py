"""
LinkedIn person profile scraping tools.

Uses innerText extraction for resilient profile data capture
with configurable section selection.
"""

import logging
from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.dependencies import Depends

from linkedin_mcp_server.constants import TOOL_TIMEOUT_SECONDS
from linkedin_mcp_server.dependencies import get_extractor
from linkedin_mcp_server.error_handler import raise_tool_error
from linkedin_mcp_server.scraping import LinkedInExtractor, parse_person_sections

logger = logging.getLogger(__name__)


def register_person_tools(mcp: FastMCP) -> None:
    """Register all person-related tools with the MCP server."""

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        title="Get Person Profile",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"person", "scraping"},
    )
    async def get_person_profile(
        linkedin_username: str,
        ctx: Context,
        sections: str | None = None,
        extractor: LinkedInExtractor = Depends(get_extractor),
    ) -> dict[str, Any]:
        """
        Get a specific person's LinkedIn profile.

        Args:
            linkedin_username: LinkedIn username (e.g., "stickerdaniel", "williamhgates")
            ctx: FastMCP context for progress reporting
            sections: Comma-separated list of extra sections to scrape.
                The main profile page is always included.
                Available sections: experience, education, interests, honors, languages, contact_info, posts
                Examples: "experience,education", "contact_info", "honors,languages", "posts"
                Default (None) scrapes only the main profile page.

        Returns:
            Dict with url, sections (name -> raw text), and optional references.
            Sections may be absent if extraction yielded no content for that page.
            Includes unknown_sections list when unrecognised names are passed.
            The LLM should parse the raw text in each section.
        """
        try:
            requested, unknown = parse_person_sections(sections)

            logger.info(
                "Scraping profile: %s (sections=%s)",
                linkedin_username,
                sections,
            )

            await ctx.report_progress(
                progress=0, total=100, message="Starting person profile scrape"
            )

            result = await extractor.scrape_person(linkedin_username, requested)

            if unknown:
                result["unknown_sections"] = unknown

            await ctx.report_progress(progress=100, total=100, message="Complete")

            return result

        except Exception as e:
            raise_tool_error(e, "get_person_profile")  # NoReturn

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        title="Search People",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"person", "search"},
    )
    async def search_people(
        keywords: str,
        ctx: Context,
        location: str | None = None,
        current_company: str | None = None,
        past_company: str | None = None,
        industry: str | None = None,
        geo_urn: str | None = None,
        extractor: LinkedInExtractor = Depends(get_extractor),
    ) -> dict[str, Any]:
        """
        Search for people on LinkedIn.

        Args:
            keywords: Search keywords (e.g., "software engineer", "recruiter at Google")
            ctx: FastMCP context for progress reporting
            location: Optional location filter (e.g., "New York", "Remote")
            current_company: Comma-separated LinkedIn company IDs to filter by current employer.
                Well-known IDs: Databricks=18373098, Snowflake=9667088, Tableau=11558,
                Salesforce=1066, Google=1441, Microsoft=1035, Amazon=1586.
                Example: "18373098" or "18373098,9667088" for multiple companies.
            past_company: Comma-separated LinkedIn company IDs to filter by past employer.
                Same IDs as current_company. Example: "11558,1066" for ex-Tableau OR ex-Salesforce.
            industry: Comma-separated LinkedIn industry IDs to filter by.
                Known IDs: Staffing and Recruiting=104, IT Services=96,
                Computer Software=4, Internet=6, Financial Services=43.
                Example: "104" or "104,96" for multiple industries.
            geo_urn: Comma-separated LinkedIn geoUrn IDs for precise location filtering.
                Overrides location when provided. Known IDs:
                Greater Toronto Area=90009551, St. Catharines-Niagara=90009548.
                Example: "90009551" or "90009551,90009548" for multiple regions.

        Returns:
            Dict with url, sections (name -> raw text), and optional references.
            The LLM should parse the raw text to extract individual people and their profiles.
        """
        try:
            logger.info(
                "Searching people: keywords='%s', location='%s', "
                "current_company='%s', past_company='%s', "
                "industry='%s', geo_urn='%s'",
                keywords,
                location,
                current_company,
                past_company,
                industry,
                geo_urn,
            )

            await ctx.report_progress(
                progress=0, total=100, message="Starting people search"
            )

            result = await extractor.search_people(
                keywords, location, current_company, past_company,
                industry, geo_urn,
            )

            await ctx.report_progress(progress=100, total=100, message="Complete")

            return result

        except Exception as e:
            raise_tool_error(e, "search_people")  # NoReturn
