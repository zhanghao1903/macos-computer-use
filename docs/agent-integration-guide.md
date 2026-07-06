# Agent Application Integration Guide

本文面向要把 `computer-use-macos` 接入自己 Agent 应用的开发者。它关注
产品侧真正会遇到的问题：如何选择接入路径、如何调用工具、macOS 权限落在哪
个进程上、token/socket 鉴权怎么设计、helper 怎么打包发布，以及如何把这些
能力接入自己的任务、确认、审计和恢复系统。

## 核心模型

这个工具包不是一个完整 Agent runtime。它只提供本机 macOS 桌面控制的确定性
能力：

- readiness 和权限检查；
- 结构化观察；
- allowlist 内的 app 打开和聚焦；
- 保守的文本输入、键盘、点击；
- 高风险动作的结构化风险元数据；
- helper 和本地 socket transport。

Agent 应用仍然需要自己拥有：

- 任务编排和 LLM planner；
- 用户确认流程；
- 业务权限判断；
- 审计、证据和回放；
- 重试、恢复和失败处理；
- UI/vision grounding fallback。

推荐生产架构：

```text
Agent App / Runtime
  -> policy + confirmation + audit
  -> computer-use-macos SDK
  -> developer-owned signed helper app
  -> macOS Accessibility / Automation / Screen Recording
  -> target desktop application
```

这条路径的关键点是：SDK 负责协议和客户端封装，helper 负责作为稳定的 macOS
权限主体执行动作。

## 选择接入路径

### 开发期：direct backend

本地开发、TextEdit smoke、早期调试可以直接让 Python 进程调用 macOS API：

```python
from computer_use_macos import ComputerUseClient

client = ComputerUseClient(
    allowed_apps={"TextEdit": "com.apple.TextEdit"},
    allow_coordinate_click=False,
)

print(client.readiness().to_dict())
print(client.open_app("TextEdit", bundle_id="com.apple.TextEdit").to_dict())
print(client.observe(target_app="TextEdit", bundle_id="com.apple.TextEdit").to_dict())
```

direct backend 的 macOS 权限授予对象是当前执行进程，例如 Terminal、IDE、
Python、Electron app 或测试 runner。这个模式适合开发，但不适合作为稳定的
最终用户权限模型，因为启动器、路径、签名或 bundle identity 变化后，macOS
TCC 权限记录可能需要重新授权。

### 生产期：helper backend

生产建议使用开发者自己打包、签名、公证的 helper：

```text
Agent App
  -> SDK
  -> helper manifest
  -> unix socket + token
  -> signed helper
  -> macOS API
```

这时 macOS 权限授予对象是 helper app 的 bundle identity，而不是 SDK。
用户在 System Settings 里给 helper 授权，SDK 只负责连接 helper 并发送协议
命令。

```python
from computer_use_macos import ComputerUseClient

client = ComputerUseClient.from_helper_manifest("./helper_config.json")
result = client.readiness()
print(result.to_dict())
```

也可以用统一配置文件：

```toml
[computer_use]
backend = "helper"
allowed_apps = ["TextEdit"]
allow_coordinate_click = false
timeout_ms = 10000

[computer_use.allowed_app_bundle_ids]
TextEdit = "com.apple.TextEdit"

[helper]
transport = "unix_socket"
helper_app_path = "/Applications/Example Computer Use Helper.app"
bundle_id = "com.example.computer-use-helper"
manifest_path = "./helper_config.json"
allowed_apps = ["TextEdit"]
auto_launch = true
launch_timeout_ms = 90000
```

```python
from computer_use_macos import ComputerUseClient

client = ComputerUseClient.from_config("app-control.toml")
```

### 非 Python 调用方：local service mode

如果你的 Agent runtime 是 Node、Go、Swift、Java 或另一个进程，可以启动本地
Unix socket service：

```bash
openssl rand -hex 24 > app-control.token
chmod 600 app-control.token

computer-use-macos serve \
  --config ./app-control.toml \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token
```

然后从另一个进程发请求：

```bash
computer-use-macos request \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token \
  --operation readiness
```

这个 service 只是本机 transport，不是远程授权系统、任务队列或审计系统。调用
方仍然要在发送命令前做业务授权和用户确认。

## SDK 调用方式

### 使用 convenience methods

适合普通应用代码：

```python
from computer_use_macos import ComputerUseClient

client = ComputerUseClient.from_config("app-control.toml")

ready = client.readiness()
if not ready.success:
    raise RuntimeError(ready.to_dict())

client.open_app("TextEdit", bundle_id="com.apple.TextEdit")
client.focus_app("TextEdit", bundle_id="com.apple.TextEdit")
snapshot = client.observe(target_app="TextEdit", bundle_id="com.apple.TextEdit")
client.type_text("hello from agent", target_app="TextEdit", bundle_id="com.apple.TextEdit")
```

direct backend 的部分 convenience methods 返回兼容旧接口的
`ComputerUseResult`。helper-backed client 通过 command/observation 边界工作，
返回 `ToolObservation`。应用侧建议统一调用 `.to_dict()` 后映射到自己的事件
和审计模型。

### 使用 protocol command

适合 Agent runtime、跨语言 transport、队列和审计系统：

```python
from app_control_protocol import ToolCommand
from computer_use_macos import ComputerUseClient

client = ComputerUseClient.from_config("app-control.toml")

command = ToolCommand(
    command_id="cmd_open_textedit_001",
    tool="macos.computer_use",
    operation="open_app",
    input={
        "app": "TextEdit",
        "bundleId": "com.apple.TextEdit",
    },
    timeout_ms=10_000,
)

observation = client.run_command(command)
print(observation.to_dict())
```

也可以使用命令 builder，避免手写 envelope：

```python
from computer_use_macos import ComputerUseClient, open_app_command

client = ComputerUseClient.from_config("app-control.toml")
observation = client.run_command(
    open_app_command("TextEdit", bundle_id="com.apple.TextEdit", timeout_ms=10_000)
)
```

### 使用 event stream

长操作或需要进度反馈时使用 `run_stream`：

```python
from computer_use_macos import ComputerUseClient, open_app_command

client = ComputerUseClient.from_config("app-control.toml")

for event in client.run_stream(
    open_app_command("TextEdit", bundle_id="com.apple.TextEdit")
):
    payload = event.to_dict() if hasattr(event, "to_dict") else event
    print(payload)
```

Agent 应用可以把 stream event 写入自己的 task log，再把最后一个 observation
作为本轮 action 的结果。

### 推荐 Agent loop

每个桌面动作都应该放在一个可恢复的闭环里：

```text
1. readiness()
2. observe() / accessibility_query()
3. planner 选择下一步
4. authorize(command)
5. 必要时 request_user_confirmation(command, risk)
6. run_command(command) 或 run_stream(command)
7. observe() 验证结果
8. 记录 command、observation、risk、用户确认和证据
9. 失败时重试、回退、请求用户介入或切换视觉 fallback
```

不要把工具调用当成一次不可验证的 fire-and-forget 操作。桌面 UI 可能被遮挡、
失焦、动画延迟、语言变化、窗口布局变化，执行后必须再次观察。

## macOS 鉴权模型

macOS 授权给实际调用系统 API 的进程，而不是授权给 Python package 或 SDK。

### direct backend

```text
Agent App / Terminal / Python
  -> SDK
  -> macOS API
```

需要授权的是 Agent App、Terminal、Python 或 IDE。

### helper backend

```text
Agent App
  -> SDK
  -> helper socket
  -> signed helper
  -> macOS API
```

需要授权的是 signed helper app。

### local service mode

```text
Agent App
  -> socket service
  -> backend process
  -> macOS API
```

需要授权的是 service backend 所在进程。如果 service 再转发到 helper，则最终
需要授权 helper。

## token 和 socket 鉴权

`socketPath` 是本地 Unix domain socket 的入口地址，例如：

```text
/tmp/example-computer-use-helper.sock
```

它不是普通数据文件。服务端 `bind/listen` 这个路径，客户端 `connect` 这个
路径。连接建立后，客户端和服务端各自拿到自己的 file descriptor，通过内核
socket buffer 双向读写。

`tokenRef` 或 `--token-file` 是本地访问口令文件，例如：

```text
/tmp/example-computer-use-helper.token
```

token 是 bearer secret。谁能读取 token，谁就能代表本地调用方访问 helper 或
service。因此：

- token 文件权限应限制为 `0600`；
- 不要提交 token 到 git；
- 不要把 token 写入日志；
- 不要把 helper socket 暴露成远程 HTTP 入口；
- token 只证明本地 caller 可以访问 transport，不代表业务动作一定允许。

推荐鉴权链路：

```text
socket filesystem permission
  -> token authentication
  -> caller profile / scopes
  -> app allowlist
  -> operation policy
  -> risk classification
  -> user confirmation when needed
  -> execute
```

当前工具包提供本地 token 校验、app allowlist、坐标点击开关和风险元数据。
如果你的产品需要多租户、组织权限、用户角色、操作额度或审批流，应在 Agent
应用或自定义 helper policy 中实现。

## 业务授权和确认边界

工具包不会决定你的业务动作是否允许。它只提供低层安全边界和结构化风险。

应用侧应该在发送命令前做：

```python
def authorize_desktop_command(user, task, command):
    if command.operation in {"click", "type_text", "press_key", "hotkey"}:
        assert task.user_approved_desktop_control

    target_app = command.input.get("targetApp") or command.input.get("app")
    if target_app not in user.allowed_desktop_apps:
        return False

    if command.operation == "click" and looks_like_submit_or_pay(command):
        return require_user_confirmation(user, task, command)

    return True
```

高风险动作包括但不限于：

- 发送、提交、支付；
- 删除、归档、覆盖；
- 安装、权限变更、系统设置；
- 密码、安全、隐私相关 UI；
- 未确认的 raw coordinate click。

即使 token 有权限，也不应该直接放行这些动作。推荐做法是 helper 或 SDK 返回
`confirmation_required` 风险元数据后，Agent 应用暂停任务，展示明确的用户确认
UI，确认通过后再发送下一条更具体、更受限的命令。

## 打包自己的 helper

### 生成 helper 模板

```bash
computer-use-macos helper init ./computer-use-helper \
  --name "Example Computer Use Helper" \
  --bundle-id com.example.computer-use-helper \
  --team-id ABCDE12345
```

生成目录包含：

```text
computer-use-helper/
  README.md
  Info.plist.template
  entitlements.plist
  helper_config.json
  build.py
  build.sh
  sign.sh
  notarize.sh
  src/helper_main.py
```

开发构建：

```bash
computer-use-macos helper build ./computer-use-helper
```

### 配置 manifest

典型 manifest：

```json
{
  "bundleId": "com.example.computer-use-helper",
  "apiVersion": "app_control.helper.v1",
  "transport": "unix_socket",
  "socketPath": "/tmp/example-computer-use-helper.sock",
  "tokenRef": "/tmp/example-computer-use-helper.token",
  "metadata": {
    "allowedApps": ["TextEdit"],
    "allowedAppBundleIds": {
      "TextEdit": "com.apple.TextEdit"
    },
    "allowCoordinateClick": false
  }
}
```

保持 allowlist 窄。空 allowlist 会让 app-targeted 操作默认拒绝，这是生产上更安
全的失败方式。

### 签名和公证

```bash
cd ./computer-use-helper
./build.sh
./sign.sh "build/computer-use-helper.app" \
  "Developer ID Application: Example Corp (ABCDE12345)"
APPLE_ID=dev@example.com \
  APP_PASSWORD=app-specific-password \
  TEAM_ID=ABCDE12345 \
  ./notarize.sh "build/computer-use-helper.app"
```

发布前验证：

```bash
computer-use-macos helper doctor \
  --manifest ./helper_config.json \
  --helper-app "/Applications/Example Computer Use Helper.app" \
  --expected-bundle-id com.example.computer-use-helper \
  --verify-signature \
  --verify-notarization \
  --json
```

签名、公证、安装位置、自动启动和更新流程由应用团队负责。helper 的 bundle id
和签名身份要稳定，否则用户授权可能需要重新授予。

## 首次运行和用户授权

推荐 onboarding 流程：

```text
1. 安装 Agent App 和 helper
2. Agent App 启动 helper 或提示用户启动
3. SDK 调 readiness()
4. 如果缺少 Accessibility，展示引导并打开 System Settings
5. 用户给 helper 授权
6. 用户重启 helper 或按产品提示重新检查
7. readiness() 返回可用
8. 执行 TextEdit 或自家 app 的 smoke action
```

`readiness()` 应该进入产品状态机，而不是只打印日志。常见状态：

- helper 未安装；
- helper 无法启动；
- socket 不存在；
- token 不可读或不匹配；
- Accessibility 未授权；
- target app 未安装或未 allowlist；
- helper bundle id 和 manifest 不匹配。

## 接入自己的 Agent 系统

一个实用的集成边界如下：

```text
agent_planner
  -> proposes ToolCommand

desktop_policy
  -> validates target app, operation, user role, task scope

confirmation_service
  -> pauses high-risk commands and records explicit approval

desktop_executor
  -> wraps ComputerUseClient and normalizes observations

evidence_store
  -> stores command, observation, timing, risk, user confirmation

recovery_controller
  -> decides retry, observe again, ask user, or abort
```

示例 adapter：

```python
from dataclasses import dataclass
from typing import Any

from app_control_protocol import ToolCommand
from computer_use_macos import ComputerUseClient


@dataclass
class DesktopActionResult:
    command_id: str
    success: bool
    status: str
    payload: dict[str, Any]


class DesktopExecutor:
    def __init__(self, config_path: str):
        self._client = ComputerUseClient.from_config(config_path)

    def run_authorized(self, command: ToolCommand) -> DesktopActionResult:
        observation = self._client.run_command(command)
        payload = observation.to_dict()
        return DesktopActionResult(
            command_id=payload.get("commandId", command.command_id),
            success=bool(payload.get("success")),
            status=str(payload.get("status")),
            payload=payload,
        )
```

不要让 LLM 直接拼 socket payload 并发送。让 LLM 产出候选意图或候选 command，
由确定性 policy 校验、补全 bundle id、限制 timeout、写入 command id 后再执
行。

## vision fallback 放在哪里

图像识别、OCR、模板匹配、视觉定位按钮、计算鼠标坐标这些能力更适合放在
Agent runtime 的 perception/action loop 中，而不是做成一个黑盒的通用工具
能力。

原因是视觉路径强依赖闭环：

```text
screenshot
  -> detect target
  -> resolve display/window/retina coordinates
  -> click or drag
  -> observe again
  -> recover if target moved or multiple matches exist
```

推荐策略：

- macOS Accessibility/API 路径作为主路径；
- vision 作为不可访问 UI、Canvas、远程桌面、图片按钮的 fallback；
- 对外暴露低层、带置信度的视觉结果；
- 是否点击、是否滚动、是否重试，由 Agent 应用根据上下文决定；
- raw coordinate click 默认关闭，只对受控 fallback 明确开启。

## 常见问题

### SDK 可以访问开发者自己打包的 helper 来闭环吗？

可以。这是推荐生产路径。开发者集成 SDK，使用自己的 bundle id、签名和公证打
包 helper，用户给 helper 授权，SDK 通过 manifest 中的 socket 和 token 访问
helper，再把 observation 交回 Agent runtime 继续规划。

### SDK 能复用工具包作者的 macOS 权限吗？

不能。macOS TCC 权限绑定实际执行进程。SDK 是库，没有独立权限身份。谁调用
Accessibility、Automation 或 Screen Recording，用户就需要给谁授权。

### token 能不能做权限分级？

可以作为入口，但不要只做 `token == admin` 的简单判断。更合理的是：

```text
token -> caller identity -> scopes -> app allowlist -> operation policy -> risk
```

当前 helper 模板提供单 token 本地校验。如果产品需要多 token、多角色或租户隔
离，可以扩展 helper policy 或在 Agent service 层做更强授权。

### socket 文件为什么能双向通信？

`socketPath` 不是普通文件，而是 Unix domain socket 的本地入口。服务端监听这
个路径，客户端连接这个路径。连接建立后，客户端和服务端各自有自己的 fd，数
据通过内核 socket buffer 双向流动，不写入这个路径对应的磁盘文件。

### 为什么不直接把 helper 开成 HTTP 服务？

默认不要这样做。桌面控制是高风险本机能力，Unix socket 加文件权限更符合本机
进程间通信模型。如果你的产品必须暴露 HTTP，需要在自己的应用层加完整认证、
授权、CSRF/来源控制、审计、确认和网络边界，不应直接转发到 helper。

### app 更新后权限失效怎么办？

保持 helper 的 bundle id、签名身份和安装路径稳定。更新后运行 doctor 和
readiness。如果 macOS 认为这是新的权限主体，产品需要引导用户重新授权。

### 为什么命令被拒绝？

常见原因：

- target app 不在 allowlist；
- bundle id 和 allowlist 不匹配；
- Accessibility 未授权；
- coordinate click 未开启；
- 命中高风险策略，需要用户确认；
- helper token 不匹配；
- socket 不存在或 helper 未启动；
- command schema 不合法；
- target app 没有前台窗口或当前状态不可操作。

先跑 helper 诊断：

```bash
computer-use-macos helper doctor ./computer-use-helper --json
```

如果你启用了 local service mode，再跑一次 socket 请求：

```bash
computer-use-macos request \
  --socket-path /tmp/app-control.sock \
  --token-file ./app-control.token \
  --operation readiness
```

再检查 observation 里的 `status`、`failureKind`、`risk`、`permissions` 和
`helper` 字段。

## 生产检查清单

发布前至少确认：

- 使用 helper backend，而不是 direct backend；
- helper bundle id、team id、签名、公证稳定；
- 用户授权对象是 helper；
- helper manifest 被打包到最终 app 或可被 SDK 发现；
- socket path 和 token path 不冲突，并限制为私有权限；
- token 不进入 git、日志、crash report 或远程 telemetry；
- app allowlist 和 bundle id 映射足够窄；
- coordinate click 默认关闭；
- high-risk action 进入用户确认流程；
- command、observation、confirmation 和错误原因进入审计；
- readiness 和 doctor 被接入安装/诊断 UI；
- 更新流程验证不会意外丢失 macOS TCC 权限；
- vision fallback 的坐标点击有额外 confirmation 或范围限制。

更多底层细节见：

- [API Contract](api.md)
- [Permissions Guide](permissions.md)
- [Helper App Lifecycle](helper-packaging.md)
- [Local Service Mode](local-service.md)
- [Protocol](protocol.md)
