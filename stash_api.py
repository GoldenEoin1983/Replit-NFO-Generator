"""
StashApp API client for direct data retrieval.

WHAT THIS FILE DOES
-------------------
Instead of exporting JSON files by hand, this module talks directly to a
running StashApp server over its GraphQL API. GraphQL is a query language
where you describe exactly which fields you want back.

The heavy lifting is done by the official 'stashapp-tools' library
(StashInterface); this class wraps it with friendlier error messages and
a few custom queries the library doesn't cover.
"""

import sys
from typing import Any
from stashapi import log
from stashapi.stashapp import StashInterface


class StashApiClient:
    """Client for connecting to and querying StashApp GraphQL API."""
    
    def __init__(self, host: str = "localhost", port: str = "9999", 
                 scheme: str = "http", api_key: str | None = None,
                 username: str | None = None, password: str | None = None):
        """
        Initialize the StashApp API client.
        
        Args:
            host: StashApp server hostname
            port: StashApp server port
            scheme: Connection scheme (http or https)
            api_key: API key for authentication
            username: Username for authentication (alternative to API key)
            password: Password for authentication (alternative to API key)
        """
        self.config = {
            "scheme": scheme,
            "host": host,
            "port": port,
            "logger": log
        }
        
        # Add authentication if provided
        if api_key:
            self.config["ApiKey"] = api_key
        elif username and password:
            self.config["username"] = username
            self.config["password"] = password
        
        try:
            self.stash = StashInterface(self.config)
            # Test connection
            self._test_connection()
        except Exception as e:  # noqa: BLE001
            raise ConnectionError(f"Failed to connect to StashApp at {scheme}://{host}:{port} - {e}")
    
    def _test_connection(self):
        """Test connection to StashApp API."""
        try:
            # Try to get system status to verify connection
            self.stash.call_GQL("query { version { version } }")
        except Exception as e:  # noqa: BLE001
            raise ConnectionError(f"Cannot connect to StashApp API: {e}")
    
    def get_scene(self, scene_id: int) -> dict[str, Any]:
        """
        Get scene data by ID.
        
        Args:
            scene_id: StashApp scene ID
            
        Returns:
            Scene data dictionary
        """
        try:
            scene_data = self.stash.find_scene(scene_id)
            if not scene_data:
                raise ValueError(f"Scene with ID {scene_id} not found")
            return scene_data
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"Failed to fetch scene {scene_id}: {e}")
    
    def get_performer(self, performer_id: int) -> dict[str, Any]:
        """
        Get performer data by ID.
        
        Args:
            performer_id: StashApp performer ID
            
        Returns:
            Performer data dictionary
        """
        try:
            performer_data = self.stash.find_performer(performer_id)
            if not performer_data:
                raise ValueError(f"Performer with ID {performer_id} not found")
            return performer_data
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"Failed to fetch performer {performer_id}: {e}")
    
    def get_gallery(self, gallery_id: int) -> dict[str, Any]:
        """
        Get gallery data by ID.
        
        Args:
            gallery_id: StashApp gallery ID
            
        Returns:
            Gallery data dictionary
        """
        try:
            # Use raw GraphQL for gallery since stashapp-tools might not have direct method
            query = """
            query FindGallery($id: ID!) {
                findGallery(id: $id) {
                    id
                    title
                    url
                    date
                    details
                    rating
                    organized
                    studio {
                        name
                    }
                    performers {
                        name
                    }
                    tags {
                        name
                    }
                    scenes {
                        id
                        title
                    }
                    folder {
                        path
                    }
                    images {
                        path
                    }
                    cover
                    created_at
                    updated_at
                }
            }
            """
            
            variables = {"id": str(gallery_id)}
            result = self.stash.call_GQL(query, variables)
            
            if not result or not result.get("findGallery"):
                raise ValueError(f"Gallery with ID {gallery_id} not found")
            
            return result["findGallery"]
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"Failed to fetch gallery {gallery_id}: {e}")
    
    def find_scene_by_path(self, file_path: str) -> dict[str, Any] | None:
        """
        Find scene by file path.
        
        Args:
            file_path: Full file path to search for
            
        Returns:
            Scene data dictionary or None if not found
        """
        try:
            query = """
            query FindScenes($filter: FindFilterType, $scene_filter: SceneFilterType) {
                findScenes(filter: $filter, scene_filter: $scene_filter) {
                    scenes {
                        id
                        title
                        files {
                            path
                        }
                    }
                }
            }
            """
            
            variables = {
                "filter": {"per_page": -1},
                "scene_filter": {"path": {"value": file_path, "modifier": "EQUALS"}}
            }
            
            result = self.stash.call_GQL(query, variables)
            scenes = result.get("findScenes", {}).get("scenes", [])
            
            if scenes:
                # Return the full scene data for the first match
                return self.get_scene(int(scenes[0]["id"]))
            
            return None
        except Exception as e:  # noqa: BLE001
            print(f"Warning: Could not search for scene by path: {e}", file=sys.stderr)
            return None
    
    def search_scenes(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Search scenes by text query.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            
        Returns:
            List of scene data dictionaries
        """
        try:
            search_query = """
            query FindScenes($filter: FindFilterType, $scene_filter: SceneFilterType) {
                findScenes(filter: $filter, scene_filter: $scene_filter) {
                    scenes {
                        id
                        title
                        studio {
                            name
                        }
                        performers {
                            name
                        }
                        files {
                            path
                        }
                    }
                }
            }
            """
            
            variables = {
                "filter": {"per_page": limit, "q": query},
                "scene_filter": {}
            }
            
            result = self.stash.call_GQL(search_query, variables)
            return result.get("findScenes", {}).get("scenes", [])
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"Failed to search scenes: {e}")
    
    def get_tag_children(self, parent: str) -> list[dict[str, Any]]:
        """
        List the child tags underneath one parent tag.

        Used by the genre feature: instead of naming every genre tag,
        the user can name ONE parent tag (e.g. "Genres") and every tag
        filed under it counts as a genre.

        Args:
            parent: Parent tag name, or its ID number as a string

        Returns:
            List of child tag dictionaries, each with 'id' and 'name'
        """
        try:
            # Step 1: turn the parent name into an ID (skip if the user
            # already gave us digits)
            if parent.isdigit():
                parent_id = parent
            else:
                find_query = """
                query FindTagByName($tag_filter: TagFilterType) {
                    findTags(tag_filter: $tag_filter, filter: {per_page: 1}) {
                        tags { id name }
                    }
                }
                """
                variables = {
                    "tag_filter": {
                        "name": {"value": parent, "modifier": "EQUALS"}
                    }
                }
                result = self.stash.call_GQL(find_query, variables)
                tags = result.get("findTags", {}).get("tags", [])
                if not tags:
                    raise ValueError(f"Parent tag '{parent}' not found in StashApp")
                parent_id = tags[0]["id"]

            # Step 2: fetch every tag whose parents include that ID
            children_query = """
            query FindChildTags($tag_filter: TagFilterType) {
                findTags(tag_filter: $tag_filter, filter: {per_page: -1}) {
                    tags { id name }
                }
            }
            """
            variables = {
                "tag_filter": {
                    "parents": {"value": [parent_id], "modifier": "INCLUDES"}
                }
            }
            result = self.stash.call_GQL(children_query, variables)
            return result.get("findTags", {}).get("tags", [])
        except ValueError:
            raise  # keep the friendly "not found" message as-is
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"Failed to look up child tags of '{parent}': {e}")

    def get_connection_info(self) -> dict[str, Any]:
        """Get connection information for display."""
        return {
            "host": self.config["host"],
            "port": self.config["port"], 
            "scheme": self.config["scheme"],
            "authenticated": "ApiKey" in self.config or ("username" in self.config and "password" in self.config)
        }