"""Release-maintainer tool. Create a NEW lock only; never update an existing lock."""
import argparse
import ast
from pathlib import Path
import shutil

from hanli_guard import CONTROL, ROOT, atomic, digest, read, runtime_info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--create-initial-lock', action='store_true', required=True)
    parser.parse_args()
    if (CONTROL / 'lock.json').exists():
        raise RuntimeError('Lock exists. Recipe changes require user approval and a separately versioned release.')
    example = ROOT / 'projects/006-hanli-reuse-10s/retry_10fps'
    CONTROL.mkdir(parents=True, exist_ok=True)
    shutil.copy2(example / 'project.json', CONTROL / 'project.example.json')
    shutil.copy2(example / 'work/render.json', CONTROL / 'render_baseline.json')
    comfy = Path('D:/work/software/pinokio/api/comfyui.pinokio/ComfyUI')
    engine = ROOT / 'GPT-SoVITS-v3lora-20250228'
    profile_name = 'projects/004-hanli-voice-finetune/approved_profile_v1.json'
    profile = read(ROOT / profile_name)
    paths = {ROOT / profile_name, CONTROL / 'project.example.json', CONTROL / 'render_baseline.json',
             ROOT / 'scripts/hanli_guard.py', ROOT / 'scripts/hanli_reuse_pipeline.py',
             ROOT / 'scripts/hanli_freeze_controls.py', ROOT / 'scripts/test_hanli_guard.py',
             ROOT / 'tools/ffmpeg-8.1.2-essentials_build/bin/ffmpeg.exe',
             ROOT / 'tools/ffmpeg-8.1.2-essentials_build/bin/ffprobe.exe',
             ROOT / read(example / 'project.json')['template'], comfy.parent / 'start_hanli_test.json',
             engine / 'GPT_SoVITS/configs/tts_infer.yaml'}
    paths.update(ROOT / profile[k] for k in ('gpt_weights', 'sovits_weights', 'character_image', 'reference_audio'))
    for folder in (engine / 'GPT_SoVITS', engine / 'tools', comfy / 'comfy', comfy / 'comfy_extras',
                   comfy / 'custom_nodes/ComfyUI-KJNodes', comfy / 'custom_nodes/ComfyUI-segment-anything-2',
                   comfy / 'custom_nodes/comfyui_controlnet_aux'):
        paths.update(folder.rglob('*.py'))
    paths.update(engine.glob('*.py'))
    paths.update(comfy.glob('*.py'))
    for folder in (engine / 'GPT_SoVITS/pretrained_models',):
        paths.update(p for p in folder.rglob('*') if p.is_file() and '.cache' not in p.parts and p.suffix != '.pyc')
    models = {
        'models/clip_vision/clip_vision_h.safetensors',
        'models/diffusion_models/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors',
        'models/loras/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors',
        'models/loras/WanAnimate_relight_lora_fp16.safetensors',
        'models/sam2/sam2_hiera_base_plus.safetensors',
        'models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors',
        'models/vae/wan_2.1_vae.safetensors',
        'custom_nodes/comfyui_controlnet_aux/ckpts/hr16/DWPose-TorchScript-BatchSize5/dw-ll_ucoco_384_bs5.torchscript.pt',
        'custom_nodes/comfyui_controlnet_aux/ckpts/yzd-v/DWPose/yolox_l.onnx',
    }
    paths.update(comfy / p for p in models)
    files = {}
    for path in sorted(paths):
        name = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix()
        if path.stat().st_size > 100_000_000:
            print('Hashing ' + name, flush=True)
        files[name] = {'bytes': path.stat().st_size, 'sha256': digest(path)}
    runtimes = {}
    for path in (engine / 'runtime/python.exe', comfy / 'env/Scripts/python.exe'):
        name = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix()
        runtimes[name] = runtime_info(path)
    version_tree = ast.parse((comfy / 'comfyui_version.py').read_text(encoding='utf-8'))
    version = next(ast.literal_eval(n.value) for n in version_tree.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == '__version__' for t in n.targets))
    comfy_runtime = runtimes[(comfy / 'env/Scripts/python.exe').as_posix()]
    # Offline expected service identity; this is not a claim that the service is online.
    system = {'comfyui_version': version, 'python_version': comfy_runtime['python'],
              'pytorch_version': comfy_runtime['packages']['torch'],
              'argv': ['main.py', '--reserve-vram', '6', '--disable-cuda-malloc',
                       '--disable-async-offload', '--disable-pinned-memory']}
    lock = dict(recipe='hanli-v1-controls-20260913', profile=profile_name, files=files, runtimes=runtimes,
                comfy_root=str(comfy),
                environment_capture='offline source and runtime inspection; live service must pass environment gate before generation',
                comfy_system={k: system[k] for k in ('comfyui_version', 'python_version', 'pytorch_version', 'argv')},
                fixed_project_fields=['seconds', 'width', 'height', 'render_fps', 'output_fps', 'profile', 'template',
                                      'label', 'lip_sync', 'audio_policy'])
    atomic(CONTROL / 'lock.json', lock)
    print('Locked', len(files), 'files. Do not regenerate this baseline to make a failing check pass.')


if __name__ == '__main__':
    main()
