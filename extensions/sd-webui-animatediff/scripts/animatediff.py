import os

# TODO uncomment this
# from scripts.animatediff_cn import AnimateDiffControl
from scripts.animatediff_infv2v import AnimateDiffInfV2V

# TODO uncomment this
# from scripts.animatediff_latent import AnimateDiffI2VLatent
from scripts.animatediff_logger import logger_animatediff as logger
from scripts.animatediff_lora import AnimateDiffLora
from scripts.animatediff_mm import mm_animatediff as motion_module
from scripts.animatediff_output import AnimateDiffOutput
from scripts.animatediff_ui import AnimateDiffProcess  # , AnimateDiffUiGroup

from modules import script_callbacks, scripts, shared
from modules.processing import Processed  # StableDiffusionProcessingImg2Img,
from modules.processing import StableDiffusionProcessing

# import gradio as gr


script_dir = scripts.basedir()
motion_module.set_script_dir(script_dir)


class AnimateDiffScript(scripts.Script):
    def __init__(self):
        self.lora_hacker = None
        self.cfg_hacker = None
        self.cn_hacker = None

    def title(self):
        return "AnimateDiff"

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def ui(self, is_img2img):
        # model_dir = shared.opts.data.get("animatediff_model_path", os.path.join(script_dir, "model"))
        # return (AnimateDiffUiGroup().render(is_img2img, model_dir),)
        return tuple()

    def before_process(self, p: StableDiffusionProcessing, params: AnimateDiffProcess):
        if isinstance(params, dict):
            params = AnimateDiffProcess(**params)
        if params.enable:
            logger.info("AnimateDiff process start.")
            params.set_p(p)
            motion_module.inject(p.sd_model, params.model)
            self.lora_hacker = AnimateDiffLora(motion_module.mm.using_v2)
            self.lora_hacker.hack()
            self.cfg_hacker = AnimateDiffInfV2V(p)
            self.cfg_hacker.hack(params)
            # TODO uncomment this
            # self.cn_hacker = AnimateDiffControl(p)
            # self.cn_hacker.hack(params)

    def before_process_batch(
        self, p: StableDiffusionProcessing, params: AnimateDiffProcess, **kwargs
    ):
        if isinstance(params, dict):
            params = AnimateDiffProcess(**params)
        # TODO uncomment this
        # if params.enable and isinstance(p, StableDiffusionProcessingImg2Img):
        #     AnimateDiffI2VLatent().randomize(p, params)

    def postprocess(
        self, p: StableDiffusionProcessing, res: Processed, params: AnimateDiffProcess
    ):
        if isinstance(params, dict):
            params = AnimateDiffProcess(**params)
        if params.enable:
            # TODO uncomment this
            # self.cn_hacker.restore()
            self.cfg_hacker.restore()
            self.lora_hacker.restore()
            motion_module.restore(p.sd_model)
            AnimateDiffOutput().output(p, res, params)
            logger.info("AnimateDiff process end.")


def on_ui_settings():
    section = ("animatediff", "AnimateDiff")
    shared.opts.add_option(
        "animatediff_model_path",
        shared.OptionInfo(
            os.path.join(script_dir, "model"),
            "Path to save AnimateDiff motion modules",
            None,
            # gr.Textbox,
            section=section,
        ),
    )
    shared.opts.add_option(
        "animatediff_optimize_gif_palette",
        shared.OptionInfo(
            False,
            "Calculate the optimal GIF palette, improves quality significantly, removes banding",
            None,
            # gr.Checkbox,
            section=section,
        ),
    )
    shared.opts.add_option(
        "animatediff_optimize_gif_gifsicle",
        shared.OptionInfo(
            False,
            "Optimize GIFs with gifsicle, reduces file size",
            None,
            # gr.Checkbox,
            section=section,
        ),
    )
    shared.opts.add_option(
        "animatediff_xformers",
        shared.OptionInfo(
            "Optimize attention layers with xformers",
            "When you have --xformers in your command line args, you want AnimateDiff to ",
            None,
            # gr.Radio,
            {
                "choices": [
                    "Optimize attention layers with xformers",
                    "Optimize attention layers with sdp (torch >= 2.0.0 required)",
                    "Do not optimize attention layers",
                ]
            },
            section=section,
        ),
    )


script_callbacks.on_ui_settings(on_ui_settings)
# script_callbacks.on_after_component(AnimateDiffUiGroup.on_after_component)