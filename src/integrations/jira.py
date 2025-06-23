"""JIRA Integration for Haven Health Passport.

This module provides integration with JIRA for issue tracking and incident management.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import (
    HTTPError,
    Timeout,
)

from src.utils.logging import get_logger

logger = get_logger(__name__)


class JIRAIssueType(Enum):
    """JIRA issue types."""

    BUG = "Bug"
    TASK = "Task"
    STORY = "Story"
    INCIDENT = "Incident"
    SECURITY = "Security"


class JIRAPriority(Enum):
    """JIRA priority levels."""

    CRITICAL = "1"
    HIGH = "2"
    MEDIUM = "3"
    LOW = "4"
    TRIVIAL = "5"


@dataclass
class JIRAConfig:
    """JIRA configuration settings."""

    base_url: str
    username: str
    api_token: str
    project_key: str = "HHP"
    default_assignee: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3
    verify_ssl: bool = True


@dataclass
class JIRAIssue:
    """JIRA issue data structure."""

    summary: str
    description: str
    issue_type: JIRAIssueType = JIRAIssueType.TASK
    priority: JIRAPriority = JIRAPriority.MEDIUM
    assignee: Optional[str] = None
    labels: List[str] = field(default_factory=list)
    components: List[str] = field(default_factory=list)
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    attachments: List[Dict[str, Any]] = field(default_factory=list)


class JIRAIntegration:
    """JIRA integration client for Haven Health Passport."""

    def __init__(self, config: JIRAConfig):
        """Initialize JIRA integration.

        Args:
            config: JIRA configuration settings
        """
        self.config = config
        self.auth = HTTPBasicAuth(config.username, config.api_token)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self._validate_connection()

    def _validate_connection(self) -> None:
        """Validate JIRA connection and credentials."""
        try:
            response = self._make_request("GET", "/myself")
            logger.info(f"Connected to JIRA as: {response.get('displayName')}")
        except Exception as e:
            logger.error(f"Failed to connect to JIRA: {e}")
            raise

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to JIRA API.

        Args:
            method: HTTP method
            endpoint: API endpoint
            data: Request data
            files: Files to upload

        Returns:
            Response data

        Raises:
            HTTPError: On API errors
            RequestsConnectionError: On connection issues
            Timeout: On request timeout
        """
        url = f"{self.config.base_url.rstrip('/')}/rest/api/3{endpoint}"

        for attempt in range(self.config.max_retries):
            try:
                if files:
                    # For file uploads, don't send JSON headers
                    response = requests.request(
                        method=method,
                        url=url,
                        auth=self.auth,
                        files=files,
                        timeout=self.config.timeout,
                        verify=self.config.verify_ssl,
                    )
                else:
                    response = requests.request(
                        method=method,
                        url=url,
                        json=data,
                        headers=self.headers,
                        auth=self.auth,
                        timeout=self.config.timeout,
                        verify=self.config.verify_ssl,
                    )

                response.raise_for_status()

                if response.content:
                    result = response.json()
                    return result if isinstance(result, dict) else {}
                return {}

            except (RequestsConnectionError, Timeout) as e:
                if attempt == self.config.max_retries - 1:
                    raise
                logger.warning(f"Request failed (attempt {attempt + 1}): {e}")

        raise RequestsConnectionError("Max retries exceeded")

    def create_issue(self, issue: JIRAIssue) -> str:
        """Create a new JIRA issue.

        Args:
            issue: Issue data

        Returns:
            Issue key (e.g., "HHP-123")

        Raises:
            HTTPError: On API errors
        """
        # Build issue data
        issue_data: Dict[str, Any] = {
            "fields": {
                "project": {"key": self.config.project_key},
                "summary": issue.summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": issue.description}],
                        }
                    ],
                },
                "issuetype": {"name": issue.issue_type.value},
                "priority": {"id": issue.priority.value},
            }
        }

        # Add optional fields
        if issue.assignee or self.config.default_assignee:
            issue_data["fields"]["assignee"] = {
                "accountId": issue.assignee or self.config.default_assignee
            }

        if issue.labels:
            issue_data["fields"]["labels"] = issue.labels

        if issue.components:
            issue_data["fields"]["components"] = [
                {"name": comp} for comp in issue.components
            ]

        # Add custom fields
        for field_id, value in issue.custom_fields.items():
            issue_data["fields"][field_id] = value

        # Create issue
        response = self._make_request("POST", "/issue", issue_data)
        issue_key = str(response["key"])

        logger.info(f"Created JIRA issue: {issue_key}")

        # Add attachments if any
        if issue.attachments:
            for attachment in issue.attachments:
                self._add_attachment(issue_key, attachment)

        return issue_key

    def update_issue(self, issue_key: str, updates: Dict[str, Any]) -> bool:
        """Update an existing JIRA issue.

        Args:
            issue_key: Issue key (e.g., "HHP-123")
            updates: Fields to update

        Returns:
            True if successful

        Raises:
            HTTPError: On API errors
        """
        update_data = {"fields": updates}

        try:
            self._make_request("PUT", f"/issue/{issue_key}", update_data)
            logger.info(f"Updated JIRA issue: {issue_key}")
            return True
        except HTTPError as e:
            logger.error(f"Failed to update issue {issue_key}: {e}")
            raise

    def add_comment(self, issue_key: str, comment: str) -> bool:
        """Add a comment to a JIRA issue.

        Args:
            issue_key: Issue key
            comment: Comment text

        Returns:
            True if successful
        """
        comment_data = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": comment}],
                    }
                ],
            }
        }

        try:
            self._make_request("POST", f"/issue/{issue_key}/comment", comment_data)
            logger.info(f"Added comment to {issue_key}")
            return True
        except HTTPError as e:
            logger.error(f"Failed to add comment to {issue_key}: {e}")
            return False

    def transition_issue(self, issue_key: str, transition_name: str) -> bool:
        """Transition an issue to a new status.

        Args:
            issue_key: Issue key
            transition_name: Name of the transition (e.g., "In Progress", "Done")

        Returns:
            True if successful
        """
        try:
            # Get available transitions
            transitions = self._make_request("GET", f"/issue/{issue_key}/transitions")

            # Find the transition ID
            transition_id = None
            for trans in transitions.get("transitions", []):
                if trans["name"].lower() == transition_name.lower():
                    transition_id = trans["id"]
                    break

            if not transition_id:
                logger.error(
                    f"Transition '{transition_name}' not found for {issue_key}"
                )
                return False

            # Execute transition
            self._make_request(
                "POST",
                f"/issue/{issue_key}/transitions",
                {"transition": {"id": transition_id}},
            )

            logger.info(f"Transitioned {issue_key} to {transition_name}")
            return True

        except HTTPError as e:
            logger.error(f"Failed to transition {issue_key}: {e}")
            return False

    def get_issue(self, issue_key: str) -> Optional[Dict[str, Any]]:
        """Get issue details.

        Args:
            issue_key: Issue key

        Returns:
            Issue data or None if not found
        """
        try:
            return self._make_request("GET", f"/issue/{issue_key}")
        except HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Issue {issue_key} not found")
                return None
            raise

    def search_issues(self, jql: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Search for issues using JQL.

        Args:
            jql: JIRA Query Language string
            max_results: Maximum number of results

        Returns:
            List of issues
        """
        search_data = {
            "jql": jql,
            "maxResults": max_results,
            "fields": [
                "summary",
                "status",
                "assignee",
                "priority",
                "created",
                "updated",
            ],
        }

        response = self._make_request("POST", "/search", search_data)
        issues = response.get("issues", [])
        return issues if isinstance(issues, list) else []

    def _add_attachment(self, issue_key: str, attachment: Dict[str, Any]) -> bool:
        """Add attachment to an issue.

        Args:
            issue_key: Issue key
            attachment: Attachment data with 'filename' and 'content'

        Returns:
            True if successful
        """
        try:
            files = {
                "file": (
                    attachment["filename"],
                    attachment["content"],
                    attachment.get("content_type", "application/octet-stream"),
                )
            }

            self._make_request("POST", f"/issue/{issue_key}/attachments", files=files)

            logger.info(f"Added attachment to {issue_key}: {attachment['filename']}")
            return True

        except (ConnectionError, ValueError, TypeError) as e:
            logger.error(f"Failed to add attachment: {e}")
            return False

    def create_webhook(self, webhook_url: str, events: List[str]) -> Optional[str]:
        """Create a webhook for JIRA events.

        Args:
            webhook_url: URL to receive webhook events
            events: List of event types to subscribe to

        Returns:
            Webhook ID if successful
        """
        webhook_data = {
            "name": f"HHP Webhook - {datetime.utcnow().isoformat()}",
            "url": webhook_url,
            "events": events,
            "filters": {
                "issue-related-events-section": f"project = {self.config.project_key}"
            },
            "excludeBody": False,
        }

        try:
            response = self._make_request("POST", "/webhook", webhook_data)
            webhook_id = response.get("id")
            logger.info(f"Created JIRA webhook: {webhook_id}")
            return webhook_id
        except HTTPError as e:
            logger.error(f"Failed to create webhook: {e}")
            return None

    def delete_webhook(self, webhook_id: str) -> bool:
        """Delete a webhook.

        Args:
            webhook_id: Webhook ID to delete

        Returns:
            True if successful
        """
        try:
            self._make_request("DELETE", f"/webhook/{webhook_id}")
            logger.info(f"Deleted webhook: {webhook_id}")
            return True
        except HTTPError as e:
            logger.error(f"Failed to delete webhook: {e}")
            return False
