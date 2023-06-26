import logging
import typing
from collections import namedtuple
from dataclasses import dataclass

from bosdyn.api import image_pb2
from bosdyn.client.image import (
    ImageClient,
    build_image_request,
    UnsupportedPixelFormatRequestedError,
)
from bosdyn.client.robot import Robot

"""List of body image sources for periodic query"""
CAMERA_IMAGE_SOURCES = [
    "frontleft_fisheye_image",
    "frontright_fisheye_image",
    "left_fisheye_image",
    "right_fisheye_image",
    "back_fisheye_image",
]
DEPTH_IMAGE_SOURCES = [
    "frontleft_depth",
    "frontright_depth",
    "left_depth",
    "right_depth",
    "back_depth",
]
DEPTH_REGISTERED_IMAGE_SOURCES = [
    "frontleft_depth_in_visual_frame",
    "frontright_depth_in_visual_frame",
    "right_depth_in_visual_frame",
    "left_depth_in_visual_frame",
    "back_depth_in_visual_frame",
]
ImageBundle = namedtuple(
    "ImageBundle", ["frontleft", "frontright", "left", "right", "back"]
)
ImageWithHandBundle = namedtuple(
    "ImageBundle", ["frontleft", "frontright", "left", "right", "back", "hand"]
)

IMAGE_SOURCES_BY_CAMERA = {
    "frontleft": {
        "visual": "frontleft_fisheye_image",
        "depth": "frontleft_depth",
        "depth_registered": "frontleft_depth_in_visual_frame",
    },
    "frontright": {
        "visual": "frontright_fisheye_image",
        "depth": "frontright_depth",
        "depth_registered": "frontright_depth_in_visual_frame",
    },
    "left": {
        "visual": "left_fisheye_image",
        "depth": "left_depth",
        "depth_registered": "left_depth_in_visual_frame",
    },
    "right": {
        "visual": "right_fisheye_image",
        "depth": "right_depth",
        "depth_registered": "right_depth_in_visual_frame",
    },
    "back": {
        "visual": "back_fisheye_image",
        "depth": "back_depth",
        "depth_registered": "back_depth_in_visual_frame",
    },
    "hand": {
        "visual": "hand_color_image",
        "depth": "hand_depth",
        "depth_registered": "hand_depth_in_hand_color_frame",
    },
}

IMAGE_TYPES = {"visual", "depth", "depth_registered"}


@dataclass(frozen=True, eq=True)
class CameraSource:
    camera_name: str
    image_types: typing.List[str]


@dataclass(frozen=True)
class ImageEntry:
    camera_name: str
    image_type: str
    image_response: image_pb2.ImageResponse


class SpotImages:
    def __init__(
        self,
        robot: Robot,
        logger: logging.Logger,
        robot_params: typing.Dict[str, typing.Any],
        robot_clients: typing.Dict[str, typing.Any],
        rgb_cameras: bool = True,
    ):
        self._robot = robot
        self._logger = logger
        self._rgb_cameras = rgb_cameras
        self._robot_params = robot_params
        self._image_client: ImageClient = robot_clients["image_client"]

        ############################################
        self._camera_image_requests = []
        for camera_source in CAMERA_IMAGE_SOURCES:
            self._camera_image_requests.append(
                build_image_request(
                    camera_source,
                    image_format=image_pb2.Image.FORMAT_RAW,
                )
            )

        self._depth_image_requests = []
        for camera_source in DEPTH_IMAGE_SOURCES:
            self._depth_image_requests.append(
                build_image_request(
                    camera_source, image_format=image_pb2.Image.FORMAT_RAW
                )
            )

        self._depth_registered_image_requests = []
        for camera_source in DEPTH_REGISTERED_IMAGE_SOURCES:
            self._depth_registered_image_requests.append(
                build_image_request(
                    camera_source, image_format=image_pb2.Image.FORMAT_RAW
                )
            )

        if self._robot.has_arm():
            self._camera_image_requests.append(
                build_image_request(
                    "hand_color_image",
                    image_format=image_pb2.Image.FORMAT_JPEG,
                    pixel_format=image_pb2.Image.PIXEL_FORMAT_RGB_U8,
                    quality_percent=50,
                )
            )
            self._depth_image_requests.append(
                build_image_request(
                    "hand_depth",
                    pixel_format=image_pb2.Image.PIXEL_FORMAT_DEPTH_U16,
                )
            )
            self._depth_registered_image_requests.append(
                build_image_request(
                    "hand_depth_in_hand_color_frame",
                    pixel_format=image_pb2.Image.PIXEL_FORMAT_DEPTH_U16,
                )
            )

        # Build image requests by camera
        self._image_requests_by_camera = {}
        for camera in IMAGE_SOURCES_BY_CAMERA:
            if camera == "hand" and not self._robot.has_arm():
                continue
            self._image_requests_by_camera[camera] = {}
            image_types = IMAGE_SOURCES_BY_CAMERA[camera]
            for image_type in image_types:
                if image_type.startswith("depth"):
                    image_format = image_pb2.Image.FORMAT_RAW
                    pixel_format = image_pb2.Image.PIXEL_FORMAT_DEPTH_U16
                else:
                    image_format = image_pb2.Image.FORMAT_JPEG
                    if camera == "hand" or self._rgb_cameras:
                        pixel_format = image_pb2.Image.PIXEL_FORMAT_RGB_U8
                    elif camera != "hand":
                        self._logger.info(
                            f"Switching {camera}:{image_type} to greyscale image format."
                        )
                        pixel_format = image_pb2.Image.PIXEL_FORMAT_GREYSCALE_U8

                source = IMAGE_SOURCES_BY_CAMERA[camera][image_type]
                self._image_requests_by_camera[camera][
                    image_type
                ] = build_image_request(
                    source,
                    image_format=image_format,
                    pixel_format=pixel_format,
                    quality_percent=75,
                )

    def get_frontleft_rgb_image(self) -> image_pb2.ImageResponse:
        try:
            return self._image_client.get_image(
                [
                    build_image_request(
                        "frontleft_fisheye_image",
                        image_format=image_pb2.Image.FORMAT_RAW,
                    )
                ]
            )[0]
        except UnsupportedPixelFormatRequestedError as e:
            self._logger.error(e)
            return None

    def get_frontright_rgb_image(self) -> image_pb2.ImageResponse:
        try:
            return self._image_client.get_image(
                [
                    build_image_request(
                        "frontright_fisheye_image",
                        image_format=image_pb2.Image.FORMAT_RAW,
                    )
                ]
            )[0]
        except UnsupportedPixelFormatRequestedError as e:
            self._logger.error(e)
            return None

    def get_left_rgb_image(self) -> image_pb2.ImageResponse:
        try:
            return self._image_client.get_image(
                [
                    build_image_request(
                        "left_fisheye_image", image_format=image_pb2.Image.FORMAT_RAW
                    )
                ]
            )[0]
        except UnsupportedPixelFormatRequestedError as e:
            self._logger.error(e)
            return None

    def get_right_rgb_image(self) -> image_pb2.ImageResponse:
        try:
            return self._image_client.get_image(
                [
                    build_image_request(
                        "right_fisheye_image", image_format=image_pb2.Image.FORMAT_RAW
                    )
                ]
            )[0]
        except UnsupportedPixelFormatRequestedError as e:
            self._logger.error(e)
            return None

    def get_back_rgb_image(self) -> image_pb2.ImageResponse:
        try:
            return self._image_client.get_image(
                [
                    build_image_request(
                        "back_fisheye_image", image_format=image_pb2.Image.FORMAT_RAW
                    )
                ]
            )[0]
        except UnsupportedPixelFormatRequestedError as e:
            self._logger.error(e)
            return None

    def get_hand_rgb_image(self):
        if not self._robot.has_arm():
            return None
        try:
            return self._image_client.get_image(
                [
                    build_image_request(
                        "hand_color_image",
                        pixel_format=image_pb2.Image.PIXEL_FORMAT_RGB_U8,
                        quality_percent=50,
                    )
                ]
            )[0]
        except UnsupportedPixelFormatRequestedError as e:
            return None

    def get_images(
        self, image_requests: typing.List[image_pb2.ImageRequest]
    ) -> typing.Optional[typing.Union[ImageBundle, ImageWithHandBundle]]:
        try:
            image_responses = self._image_client.get_image(image_requests)
        except UnsupportedPixelFormatRequestedError as e:
            self._logger.error(e)
            return None
        if self._robot.has_arm():
            return ImageWithHandBundle(
                frontleft=image_responses[0],
                frontright=image_responses[1],
                left=image_responses[2],
                right=image_responses[3],
                back=image_responses[4],
                hand=image_responses[5],
            )
        else:
            return ImageBundle(
                frontleft=image_responses[0],
                frontright=image_responses[1],
                left=image_responses[2],
                right=image_responses[3],
                back=image_responses[4],
            )

    def get_camera_images(
        self,
    ) -> typing.Optional[typing.Union[ImageBundle, ImageWithHandBundle]]:
        return self.get_images(self._camera_image_requests)

    def get_depth_images(
        self,
    ) -> typing.Optional[typing.Union[ImageBundle, ImageWithHandBundle]]:
        return self.get_images(self._depth_image_requests)

    def get_depth_registered_images(
        self,
    ) -> typing.Optional[typing.Union[ImageBundle, ImageWithHandBundle]]:
        return self.get_images(self._depth_registered_image_requests)

    def get_images_by_cameras(
        self, camera_sources: typing.List[CameraSource]
    ) -> typing.Optional[typing.List[ImageEntry]]:
        """Calls the GetImage RPC using the image client with requests
        corresponding to the given cameras.
        Args:
           camera_sources: a list of CameraSource objects. There are two
               possibilities for each item in this list. Either it is
               CameraSource(camera='front') or
               CameraSource(camera='front', image_types=['visual', 'depth_registered')
                - If the former is provided, the image requests will include all
                  image types for each specified camera.
                - If the latter is provided, the image requests will be
                  limited to the specified image types for each corresponding
                  camera.
              Note that duplicates of camera names are not allowed.
        Returns:
            a list, where each entry is (camera_name, image_type, image_response)
                e.g. ('frontleft', 'visual', image_response), or none if there was an error
        """
        # Build image requests
        image_requests = []
        source_types = []
        cameras_specified = set()
        for item in camera_sources:
            if item.camera_name in cameras_specified:
                self._logger.error(
                    f"Duplicated camera source for camera {item.camera_name}"
                )
                return None
            image_types = item.image_types
            if image_types is None:
                image_types = IMAGE_TYPES
            for image_type in image_types:
                try:
                    image_requests.append(
                        self._image_requests_by_camera[item.camera_name][image_type]
                    )
                except KeyError:
                    self._logger.error(
                        f"Unexpected camera name '{item.camera_name}' or image type '{image_type}'"
                    )
                    return None
                source_types.append((item.camera_name, image_type))
            cameras_specified.add(item.camera_name)

        # Send image requests
        try:
            image_responses = self._image_client.get_image(image_requests)
        except UnsupportedPixelFormatRequestedError:
            self._logger.error(
                "UnsupportedPixelFormatRequestedError. "
                "Likely pixel_format is set wrong for some image request"
            )
            return None

        # Return
        result = []
        for i, (camera_name, image_type) in enumerate(source_types):
            result.append(
                ImageEntry(
                    camera_name=camera_name,
                    image_type=image_type,
                    image_response=image_responses[i],
                )
            )
        return result
