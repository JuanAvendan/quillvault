"""Line-crop extraction from detector polygons."""

from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray

from quillvault.types import Polygon


def crop_polygon(
    image: NDArray[np.uint8], polygon: Polygon, pad: float = 0.12
) -> NDArray[np.uint8]:
    """Perspective-rectify a quadrilateral line box, with extra vertical room for descenders."""
    pts = np.array(polygon, dtype=np.float32)
    if len(pts) != 4:
        x, y, w, h = cv2.boundingRect(pts)
        return image[y : y + h, x : x + w].copy()

    width = int(max(np.linalg.norm(pts[0] - pts[1]), np.linalg.norm(pts[3] - pts[2])))
    height = int(max(np.linalg.norm(pts[0] - pts[3]), np.linalg.norm(pts[1] - pts[2])))
    if width < 2 or height < 2:
        return np.full((2, 2, 3), 255, dtype=np.uint8)

    center = pts.mean(axis=0)
    grown = center + (pts - center) * np.array([1.0 + pad / 2, 1.0 + pad * 2], dtype=np.float32)
    target = np.array([[0, 0], [width, 0], [width, height], [0, height]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(grown.astype(np.float32), target)
    return cv2.warpPerspective(image, matrix, (width, height), borderMode=cv2.BORDER_REPLICATE)
