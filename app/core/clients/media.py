"""
Nyxen API client for media upload and authentication.
"""

import httpx
import logging
from typing import Optional, Any, TypedDict
from dataclasses import dataclass
from datetime import datetime
import time

from ..config.settings import get_s3_settings

logger = logging.getLogger(__name__)


@dataclass
class NyxenMediaUploadResponse(TypedDict):
    """Response from Nyxen media upload API"""
    id: str
    filename: str
    originalname: str
    mimetype: str
    size: int
    bucket: str
    public: bool
    created_at: datetime


class NyxenAuthResponse(TypedDict):
    """Response from Nyxen auth API"""
    token: str


class NyxenAPIException(Exception):
    """Custom exception for Nyxen API errors"""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[dict[str, Any]] = None
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class NyxenAPIClient:
    """
    Client for interacting with Nyxen API for media upload and
    authentication. Handles authentication, token refresh, and media
    operations.
    """

    def __init__(self) -> None:
        self.settings = get_s3_settings()
        self.base_url = self.settings.base_url.rstrip("/")
        self._bearer_token: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                follow_redirects=True
            )
        return self._client

    async def close(self):
        """Close the HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _login(self) -> None:
        """Perform login and get authentication tokens"""
        client = await self._get_client()

        login_data = {
            "email": self.settings.user,
            "password": self.settings.password
        }

        try:
            response = await client.post(
                f"{self.base_url}/auth/login",
                json=login_data,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()

            auth_data: NyxenAuthResponse = response.json()

            # Store tokens
            self._bearer_token = auth_data["token"]
            logger.info("Successfully logged into Nyxen API")

        except httpx.HTTPStatusError as e:
            error_msg = f"Login failed with status {e.response.status_code}"
            try:
                error_data = e.response.json()
                error_msg += f": {error_data.get('message', 'Unknown error')}"
            except Exception:
                error_msg += f": {e.response.text}"

            logger.error(error_msg)
            raise NyxenAPIException(error_msg, e.response.status_code)

        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            raise NyxenAPIException(f"Login failed: {str(e)}")

    async def _refresh_bearer_token(self) -> None:
        """Refresh the authentication token"""
        client = await self._get_client()

        try:
            response = await client.post(f"{self.base_url}/auth/refresh")
            response.raise_for_status()

            auth_data: NyxenAuthResponse = response.json()

            # Update tokens
            self._bearer_token = auth_data["token"]
            logger.info("Successfully refreshed Nyxen API token")

        except httpx.HTTPStatusError as e:
            if e.response.status_code in [401, 403]:
                logger.warning("Refresh token expired, performing full login")
                return await self._login()

            error_msg = (
                f"Token refresh failed with status {e.response.status_code}"
            )
            try:
                error_data = e.response.json()
                error_msg += f": {error_data.get('message', 'Unknown error')}"
            except Exception:
                error_msg += f": {e.response.text}"

            logger.error(error_msg)
            raise NyxenAPIException(error_msg, e.response.status_code)

        except Exception as e:
            logger.error(f"Token refresh failed: {str(e)}")
            raise NyxenAPIException(f"Token refresh failed: {str(e)}")

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid authentication token"""
        if not self._bearer_token:
            await self._login()
        else:
            await self._refresh_bearer_token()

    async def upload_audio_file(
        self,
        file_content: bytes,
        filename: str,
        mimetype: str = "audio/mpeg"
    ) -> NyxenMediaUploadResponse:
        """
        Upload an audio file to Nyxen media service.

        Args:
            file_content: Audio file content as bytes
            filename: Original filename
            mimetype: MIME type of the file

        Returns:
            NyxenMediaUploadResponse with upload details
        """
        await self._ensure_authenticated()
        client = await self._get_client()

        # Prepare multipart form data
        files = {
            "file": (filename, file_content, mimetype)
        }

        headers = {
            "Authorization": f"Bearer {self._bearer_token}"
        }

        url = f"{self.base_url}/media"
        params = {"clientSlug": self.settings.bucket}

        try:
            logger.info(
                f"Uploading audio file '{filename}' to Nyxen media service"
            )
            start_time = time.time()

            response = await client.post(
                url,
                files=files,
                headers=headers,
                params=params
            )
            response.raise_for_status()

            upload_time = time.time() - start_time
            logger.info(
                f"Successfully uploaded audio file in {upload_time:.2f} "
                "seconds"
            )

            return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code in [401, 403]:
                logger.warning(
                    "Authentication failed during upload, "
                    "refreshing token and retrying"
                )
                await self._refresh_bearer_token()

                # Retry with new token
                headers["Authorization"] = f"Bearer {self._bearer_token}"
                response = await client.post(
                    url,
                    files=files,
                    headers=headers,
                    params=params
                )
                response.raise_for_status()

                return response.json()

            error_msg = (
                f"File upload failed with status {e.response.status_code}"
            )
            try:
                error_data = e.response.json()
                error_msg += f": {error_data.get('message', 'Unknown error')}"
            except Exception:
                error_msg += f": {e.response.text}"

            logger.error(error_msg)
            raise NyxenAPIException(error_msg, e.response.status_code)

        except Exception as e:
            logger.error(f"File upload failed: {str(e)}")
            raise NyxenAPIException(f"File upload failed: {str(e)}")

    async def get_media_file_url(self, file_id: str) -> str:
        """
        Get the URL for a media file by its ID.

        Args:
            file_id: The media file ID from upload response

        Returns:
            URL to access the media file
        """
        return f"{self.base_url}/media/{file_id}"

    async def download_media_file(self, file_id: str) -> bytes:
        """
        Download a media file by its ID.

        Args:
            file_id: The media file ID

        Returns:
            File content as bytes
        """
        await self._ensure_authenticated()
        client = await self._get_client()

        url = f"{self.base_url}/media/{file_id}"
        headers = {
            "Authorization": f"Bearer {self._bearer_token}"
        }

        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.content

        except httpx.HTTPStatusError as e:
            if e.response.status_code in [401, 403]:
                await self._refresh_bearer_token()
                headers["Authorization"] = f"Bearer {self._bearer_token}"
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return response.content

            error_msg = (
                f"File download failed with status {e.response.status_code}"
            )
            logger.error(error_msg)
            raise NyxenAPIException(error_msg, e.response.status_code)

        except Exception as e:
            logger.error(f"File download failed: {str(e)}")
            raise NyxenAPIException(f"File download failed: {str(e)}")
