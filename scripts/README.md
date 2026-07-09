# scripts

| 脚本 | 作用 | 用法 |
|------|------|------|
| `new_project.ps1` | 从模板建新视频项目 | `./scripts/new_project.ps1 -Name "002-xxx"` |
| `compose.ps1` | ffmpeg 合成:换脸视频 + 新配音 → 成片 | `./scripts/compose.ps1 -Video 换脸.mp4 -Audio 配音.wav -Out 成片.mp4` |

换脸(FaceFusion)和换声(GPT-SoVITS)在各自 WebUI 里操作,不走脚本;脚本只管建项目和最后合成。后续量产可加 `project.yaml` 驱动的批处理脚本。
