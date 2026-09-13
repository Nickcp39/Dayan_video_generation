# ComfyUI 工作流位置

当前有效 API 图随配方与样片保存：

- 换皮完整基线：`workflows/hanli-v1/render_baseline.json`。
- 换皮 worker 的历史模板依赖：`projects/003-hanli-seller-10s/work/seller_a_render.json`，仍被引用，所以保留。
- 直接生成 Wan5B 模板：`projects/007-hanli-tea-dog/templates/wan5b_api.json`。
- 直接生成已执行的图片/视频图：`projects/007-hanli-tea-dog/workflows`。

这些是 HTTP API 格式，不保证能作为前端画布图直接拖入。通过对应 pipeline 构造/提交；模型权重保存在本地 ComfyUI 的 models 目录，不入 Git。

当前未验收独立口型模型；旧口型路线不作为本版运行步骤。
