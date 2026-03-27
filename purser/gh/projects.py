"""GitHub Projects v2 API wrapper via gh CLI (GraphQL)."""

from __future__ import annotations

from typing import Any

from purser.gh.cli import gh_graphql


def find_project(owner: str, project_name_or_number: str) -> dict[str, Any] | None:
    """Find a project by name or number for an owner (user or org).

    Returns the project node with id, title, number, or None if not found.
    """
    # Try as number first
    try:
        number = int(project_name_or_number)
        query = """
        query($owner: String!, $number: Int!) {
          user(login: $owner) {
            projectV2(number: $number) {
              id
              title
              number
            }
          }
        }
        """
        data = gh_graphql(query, variables={"owner": owner, "number": str(number)})
        proj = data.get("user", {}).get("projectV2")
        if proj:
            return proj
        # Try as org
        query_org = query.replace("user(login:", "organization(login:").replace(
            "user", "organization", 1
        )
        data = gh_graphql(query_org, variables={"owner": owner, "number": str(number)})
        return data.get("organization", {}).get("projectV2")
    except (ValueError, TypeError):
        pass

    # Search by name — list recent projects and match
    query = """
    query($owner: String!) {
      user(login: $owner) {
        projectsV2(first: 50) {
          nodes { id title number }
        }
      }
    }
    """
    data = gh_graphql(query, variables={"owner": owner})
    nodes = data.get("user", {}).get("projectsV2", {}).get("nodes", [])
    for node in nodes:
        if node.get("title") == project_name_or_number:
            return node
    return None


def add_item_to_project(project_id: str, content_id: str) -> str:
    """Add a GitHub issue/PR to a project. Returns the project item ID."""
    query = """
    mutation($projectId: ID!, $contentId: ID!) {
      addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
        item { id }
      }
    }
    """
    data = gh_graphql(query, variables={"projectId": project_id, "contentId": content_id})
    return data["addProjectV2ItemById"]["item"]["id"]


def get_project_fields(project_id: str) -> list[dict[str, Any]]:
    """Get all fields for a project."""
    query = """
    query($projectId: ID!) {
      node(id: $projectId) {
        ... on ProjectV2 {
          fields(first: 50) {
            nodes {
              ... on ProjectV2Field { id name dataType }
              ... on ProjectV2SingleSelectField {
                id name dataType
                options { id name }
              }
              ... on ProjectV2IterationField { id name dataType }
            }
          }
        }
      }
    }
    """
    data = gh_graphql(query, variables={"projectId": project_id})
    return data.get("node", {}).get("fields", {}).get("nodes", [])


def set_field_value(
    project_id: str,
    item_id: str,
    field_id: str,
    value: dict[str, Any],
) -> None:
    """Set a field value on a project item.

    value should be like: {"text": "..."} or {"singleSelectOptionId": "..."}
    or {"number": 1} or {"date": "2024-01-01"}.
    """
    query = """
    mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $value: ProjectV2FieldValue!) {
      updateProjectV2ItemFieldValue(input: {
        projectId: $projectId
        itemId: $itemId
        fieldId: $fieldId
        value: $value
      }) {
        projectV2Item { id }
      }
    }
    """
    gh_graphql(
        query,
        variables={
            "projectId": project_id,
            "itemId": item_id,
            "fieldId": field_id,
            "value": value,
        },
    )


def create_field(
    project_id: str,
    name: str,
    data_type: str = "TEXT",
) -> dict[str, Any]:
    """Create a new field on a project.

    data_type: TEXT, NUMBER, DATE, SINGLE_SELECT, ITERATION
    """
    query = """
    mutation($projectId: ID!, $name: String!, $dataType: ProjectV2CustomFieldType!) {
      createProjectV2Field(input: {
        projectId: $projectId
        name: $name
        dataType: $dataType
      }) {
        projectV2Field { ... on ProjectV2Field { id name dataType } }
      }
    }
    """
    data = gh_graphql(
        query,
        variables={
            "projectId": project_id,
            "name": name,
            "dataType": data_type,
        },
    )
    return data.get("createProjectV2Field", {}).get("projectV2Field", {})
