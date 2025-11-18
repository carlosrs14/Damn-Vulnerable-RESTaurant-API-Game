import base64
from urllib.parse import urlparse

import requests
from apis.menu import schemas
from db.models import MenuItem
from fastapi import HTTPException, status

ALLOWED_IMAGE_DOMAINS = [
    "images.unsplash.com",
]  # Example allow-list
ALLOWED_IMAGE_CONTENT_TYPES = ["image/jpeg", "image/png", "image/gif"]


def _image_url_to_base64(image_url: str):
    try:
        parsed_url = urlparse(image_url)
        if parsed_url.scheme not in ["http", "https"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid URL scheme.",
            )

        if parsed_url.hostname not in ALLOWED_IMAGE_DOMAINS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Domain '{parsed_url.hostname}' is not on the allow-list for images.",
            )

        response = requests.get(image_url, stream=True, allow_redirects=False, timeout=5)
        response.raise_for_status()  # Raise an exception for bad status codes

        content_type = response.headers.get("Content-Type")
        if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid content type: {content_type}. Only images are allowed.",
            )

        # To avoid downloading large files, we can check the content length
        if int(response.headers.get("Content-Length", 0)) > 5 * 1024 * 1024:  # 5MB limit
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image file size is too large.",
            )

        encoded_image = base64.b64encode(response.content).decode()
        return encoded_image

    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to fetch image: {e}"
        )



def create_menu_item(
    db,
    menu_item: schemas.MenuItemCreate,
):
    menu_item_dict = menu_item.dict()
    image_url = menu_item_dict.pop("image_url", None)
    db_item = MenuItem(**menu_item_dict)

    if image_url:
        db_item.image_base64 = _image_url_to_base64(image_url)

    db.add(db_item)
    db.commit()
    db.refresh(db_item)

    return db_item


def update_menu_item(
    db,
    item_id: int,
    menu_item: schemas.MenuItemCreate,
):
    db_item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if db_item is None:
        raise HTTPException(status_code=404, detail="Menu item not found")

    menu_item_dict = menu_item.dict()
    image_url = menu_item_dict.pop("image_url", None)

    for key, value in menu_item_dict.items():
        setattr(db_item, key, value)

    if image_url:
        db_item.image_base64 = _image_url_to_base64(image_url)

    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def delete_menu_item(db, item_id: int):
    db_item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if db_item is None:
        raise HTTPException(status_code=404, detail="Menu item not found")

    db.delete(db_item)
    db.commit()
