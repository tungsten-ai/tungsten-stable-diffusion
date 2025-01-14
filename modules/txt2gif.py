import itertools
import os
import shutil
from typing import List, Optional, Tuple, Union

import numpy as np
from tungstenkit import Image

SD_GENERATED_IMG_SIZES = [512, 768]
SD_SCALE_FACTORS = range(1, 5)
SD_AVAILABLE_IMG_SIZES = [
    size * scale_factor
    for size in SD_GENERATED_IMG_SIZES
    for scale_factor in SD_SCALE_FACTORS
]

SDXL_GENERATED_IMG_SIZES = [
    640,
    768,
    832,
    880,
    896,
    1024,
    1152,
    1168,
    1216,
    1280,
    1344,
    1536,
]
SDXL_SCALE_FACTORS = range(1, 3)
SDXL_AVAILABLE_IMG_SIZES = [
    size * scale_factor
    for size in SDXL_GENERATED_IMG_SIZES
    for scale_factor in SDXL_SCALE_FACTORS
]


def txt2gif(
    prompt: str,
    negative_prompt: str,
    seed: float | int,
    sampler_name: str,
    steps: int,
    cfg_scale: float,
    width: int,
    height: int,
    clip_skip: int,
    model_name: str,
    gif_fps: int,
    gif_frames_count: int,
    controlnet_pose_image: Optional[Image] = None,
    controlnet_depth_image: Optional[Image] = None,
    controlnet_reference_only_image: Optional[Image] = None,
    loras: Optional[List[Tuple[str, float]]] = None,
    trigger_words: Optional[List[str]] = None,
    extra_negative_prompt_chunks: Optional[List[Union[str, Tuple[str, float]]]] = None,
    extra_positive_prompt_chunks: Optional[List[Union[str, Tuple[str, float]]]] = None,
) -> List[Image]:
    from modules import prompt_utils, scripts, shared
    from modules.processing import StableDiffusionProcessingTxt2Img, process_images

    controlnet_counts = sum(
        cn is not None
        for cn in [
            controlnet_pose_image,
            controlnet_depth_image,
            controlnet_reference_only_image,
        ]
    )

    # Modify positive/negative prompts
    if extra_negative_prompt_chunks:
        for embedding in extra_negative_prompt_chunks:
            negative_prompt = prompt_utils.suppress_plain_keyword(
                embedding if isinstance(embedding, str) else embedding[0],
                negative_prompt,
            )
        for embedding in extra_negative_prompt_chunks:
            negative_prompt_increment = (
                embedding
                if isinstance(embedding, str)
                else f"({embedding[0]}:{embedding[1]})"
            )
            if negative_prompt:
                negative_prompt += ", " + negative_prompt_increment
            else:
                negative_prompt = negative_prompt_increment

    if trigger_words:
        for word in trigger_words:
            prompt = prompt_utils.suppress_plain_keyword(word, prompt)
            prompt = word + prompt

    if extra_positive_prompt_chunks:
        for embedding in extra_positive_prompt_chunks:
            prompt = prompt_utils.suppress_plain_keyword(
                embedding if isinstance(embedding, str) else embedding[0], prompt
            )
        for embedding in extra_positive_prompt_chunks:
            prompt += (
                f", {embedding}"
                if isinstance(embedding, str)
                else f", ({embedding[0]}:{embedding[1]})"
            )

    if loras:
        for lora_keyword, _ in loras:
            prompt = prompt_utils.suppress_lora_keyword(lora_keyword, prompt)
        for lora_keyword, lora_weight in loras:
            prompt += f", <lora:{lora_keyword}:{lora_weight}>"

    # Upscaler config
    (gen_width, gen_height), scale_factor = _get_generated_image_size_and_scale_factor(
        shared.sd_model, width, height
    )

    # Prepare processing
    shared.opts.set("CLIP_stop_at_last_layers", clip_skip)
    # print("Full positive prompt:", prompt)
    # print("Full negative prompt", negative_prompt)
    processing = StableDiffusionProcessingTxt2Img(
        sd_model=shared.sd_model,
        prompt=prompt,
        negative_prompt=negative_prompt,
        seed=float(seed),
        sampler_name=sampler_name,
        batch_size=1,
        steps=steps,
        cfg_scale=cfg_scale,
        width=gen_width,
        height=gen_height,
        override_settings={},
    )

    processing.scripts = scripts.scripts_txt2img
    processing.script_args = [
        dict(
            model=model_name,
            enable=True,
            video_length=gif_frames_count,
            fps=gif_fps,
            loop_number=0,
            closed_loop=False,
            batch_size=16,
            stride=1,
            overlap=4,
            format=["GIF", "PNG"],
            interp="Off",
            interp_x=10,
            reverse=[],
            video_source=None,
            video_path="output.gif",
            latent_power=1,
            latent_scale=32,
            last_frame=None,
            latent_power_last=1,
            latent_scale_last=32,
        )
    ]

    # Controlnet script
    # processing.script_args.append(
    #     {
    #         "enabled": controlnet_pose_image is not None,
    #         "module": "openpose",
    #         "model": "controlnetxlCNXL_tencentarcOpenpose"
    #         if shared.sd_model.is_sdxl
    #         else "controlnet11Models_openpose",
    #         "weight": 1.0 / controlnet_counts if controlnet_counts > 0 else 1,
    #         "image": {
    #             "image": np.array(controlnet_pose_image.to_pil_image("RGB")).astype(
    #                 "uint8"
    #             )
    #             if controlnet_pose_image is not None
    #             else None,
    #             "mask": None,
    #         },
    #         "resize_mode": "Crop and Resize",
    #         "lowvram": False,
    #         "processor_res": 512,
    #         "threshold_a": -1,
    #         "threshold_b": -1,
    #         "guidance_start": 0.0,
    #         "guidance_end": 1.0,
    #         "control_mode": "Balanced",
    #         "pixel_perfect": False,
    #         "input_mode": "simple",
    #         "batch_images": "",
    #         "output_dir": "",
    #         "loopback": False,
    #     }
    # )
    # processing.script_args.append(
    #     {
    #         "enabled": controlnet_depth_image is not None,
    #         "module": "depth",
    #         "model": "controlnetxlCNXL_tencentarcDepthMidas"
    #         if shared.sd_model.is_sdxl
    #         else "controlnet11Models_depth",
    #         "weight": 1.0 / controlnet_counts if controlnet_counts > 0 else 1,
    #         "image": {
    #             "image": np.array(controlnet_depth_image.to_pil_image("RGB")).astype(
    #                 "uint8"
    #             )
    #             if controlnet_depth_image is not None
    #             else None,
    #             "mask": None,
    #         },
    #         "resize_mode": "Crop and Resize",
    #         "lowvram": False,
    #         "processor_res": 512,
    #         "threshold_a": -1,
    #         "threshold_b": -1,
    #         "guidance_start": 0.0,
    #         "guidance_end": 1.0,
    #         "control_mode": "Balanced",
    #         "pixel_perfect": False,
    #         "input_mode": "simple",
    #         "batch_images": "",
    #         "output_dir": "",
    #         "loopback": False,
    #     }
    # )
    # processing.script_args.append(
    #     {
    #         "enabled": controlnet_reference_only_image is not None,
    #         "module": "reference_only",
    #         "model": None,
    #         "weight": 1.0 / controlnet_counts if controlnet_counts > 0 else 1,
    #         "image": {
    #             "image": np.array(
    #                 controlnet_reference_only_image.to_pil_image("RGB")
    #             ).astype("uint8")
    #             if controlnet_reference_only_image is not None
    #             else None,
    #             "mask": None,
    #         },
    #         "resize_mode": "Crop and Resize",
    #         "lowvram": False,
    #         "processor_res": -1,
    #         "threshold_a": 0.5,
    #         "threshold_b": -1,
    #         "guidance_start": 0.0,
    #         "guidance_end": 1.0,
    #         "control_mode": "Balanced",
    #         "pixel_perfect": False,
    #         "input_mode": "simple",
    #         "batch_images": "",
    #         "output_dir": "",
    #         "loopback": False,
    #     }
    # )

    # Do processing
    processed = process_images(processing)

    processing.close()

    output_path = processed.images[0]
    if os.path.exists("output.gif"):
        os.remove("output.gif")
    shutil.move(output_path, "output.gif")

    return Image.from_path("output.gif")


def _get_generated_image_size_and_scale_factor(
    model, desired_width: int, desired_height: int
):
    available_img_sizes = _get_available_img_sizes(model.is_sdxl)
    generated_img_sizes = _get_possible_generated_img_sizes(model.is_sdxl)

    assert (
        desired_height in available_img_sizes
    ), f"Invalid image height. Available heights: {available_img_sizes}"
    assert (
        desired_width in available_img_sizes
    ), f"Invalid image width. Available widths: {available_img_sizes}"
    scale_factor, width, height = 1, desired_width, desired_height
    if (
        desired_width not in generated_img_sizes
        or desired_height not in generated_img_sizes
    ):
        for _width, _height in itertools.product(
            generated_img_sizes, generated_img_sizes
        ):
            if (
                desired_width % _width == 0
                and desired_height % _height == 0
                and desired_width // _width == desired_height // _height
            ):
                scale_factor = desired_width // _width
                width = _width
                height = _height
                break
    return (width, height), scale_factor


def _get_available_img_sizes(is_sdxl: bool):
    return SDXL_AVAILABLE_IMG_SIZES if is_sdxl else SD_AVAILABLE_IMG_SIZES


def _get_possible_generated_img_sizes(is_sdxl: bool):
    return SDXL_GENERATED_IMG_SIZES if is_sdxl else SD_GENERATED_IMG_SIZES
