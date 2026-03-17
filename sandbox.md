
目录
1. 执行摘要
2. 市场背景
3. 分层全景图
4. Layer 0：隔离原语
5. Layer 1：沙箱运行时与 SDK
6. Layer 2：沙箱平台服务
7. Layer 3：专项沙箱
8. Layer 4：Agent 市场与编排平台
9. 全景对比矩阵
10. 技术趋势与演进方向
11. 机会分析
12. 附录

1. 执行摘要
AI Agent 正在从"对话式助手"演变为"自主执行者"——它们需要运行代码、操作浏览器、读写文件、调用外部工具。这一转变催生了一个快速增长的沙箱基础设施生态。
核心发现：
● 市场升温：2025-2026 年间，E2B（$21M Series A）、Daytona（$24M Series A）等沙箱公司密集融资，全球 AI Agent 市场规模 2025 年达 $7.6B。
● 技术分层清晰：生态已形成 5 层架构——隔离原语 → 运行时/SDK → 平台服务 → 专项沙箱 → Agent 市场。每层有明确的技术选型和竞争格局。
● Firecracker 成为事实标准：E2B、Vercel Sandbox、Sprites（Fly.io）、Deno Sandbox 均基于 Firecracker microVM，这一技术路线已在 Agent 沙箱领域占据主导地位。
● 三大新兴趋势：Checkpoint/Restore（状态快照恢复）预计 2027 年成为标配；Computer Use（桌面/浏览器自动化）2026 年快速普及；WASM 作为轻量隔离层在特定场景崭露头角。
● 关键空白：当前生态缺少一个将 sandbox + skills 组合为可复用垂直 Agent 并形成市场（marketplace）的开放平台。
┌──────────────────────────────────────────────────────────────┐
│  Layer 4: Agent 市场与编排平台                                 │
│  OnlyVercel · AgentDeploy · AgentSphere · Jenova              │
├──────────────────────────────────────────────────────────────┤
│  Layer 3: 专项沙箱（MCP / Browser / Computer Use）            │
│  MCP Jail · e2b-mcp · Browserbase · Steel · Firecrawl         │
│  Anthropic srt · Matchlock · Daytona Computer Use             │
├──────────────────────────────────────────────────────────────┤
│  Layer 2: 沙箱平台服务（托管 / 自托管）                         │
│  E2B · Daytona · Sprites · Modal · Vercel Sandbox             │
│  Deno Sandbox · OpenSandbox · K8s Agent Sandbox · Northflank  │
├──────────────────────────────────────────────────────────────┤
│  Layer 1: 沙箱运行时与 SDK                                     │
│  Ouros · Enclave · Code Sandbox MCP · Agent Tool Sandbox       │
│  NanoClaw · LangChain Deep Agents                             │
├──────────────────────────────────────────────────────────────┤
│  Layer 0: 隔离原语                                             │
│  Firecracker · gVisor · Kata Containers · WASM/WASI           │
│  Bubblewrap · seccomp · Landlock · Linux namespaces/cgroups   │
└──────────────────────────────────────────────────────────────┘

2. 市场背景
2.1 市场规模与增速
全球 AI Agent 市场 2025 年规模约 $7.6B（2024 年$5.4B），同比增长约 40%。Gartner 预测到 2026 年底，40% 的企业应用将嵌入 AI Agent。57% 的企业已在生产环境运行 AI Agent。
沙箱基础设施作为 Agent 执行的必要底座，正随着 Agent 市场整体增长而快速扩张。
2.2 融资热度
公司	轮次	金额	时间	领投	关键客户
E2B	Series A	$21M	2025.07	Insight Partners	88% Fortune 100、Hugging Face、Perplexity、Manus
Daytona	Series A	$24M	2026.02	FirstMark Capital	LangChain、Turing、Writer、SambaNova
Browserbase	Series A	未披露	2025	—	SOC-2/HIPAA 合规企业客户
2.3 核心驱动力
1. Agent 自主执行需求爆发：从 ChatGPT 式对话到 Manus/Devin 式自主操作，Agent 需要真正的计算环境而非模拟。
2. 安全合规压力：96.4% 的 MCP server 存在可利用漏洞（MCP Jail 审计数据），企业无法容忍 Agent 在无隔离环境执行。
3. 多租户基础设施需求：SaaS 形态的 AI 产品需要为每个用户/每次会话提供独立的隔离环境。
4. Computer Use 能力兴起：Anthropic Claude、OpenAI 等推动 Agent 操作桌面/浏览器，需要更完整的沙箱环境。

3. 分层全景图
整个 AI Agent 沙箱生态可分为 5 层，每层解决不同层面的问题，上层依赖下层。
层级	定义	核心问题
Layer 0	隔离原语	如何在操作系统/硬件层面实现进程或环境隔离？
Layer 1	沙箱运行时与 SDK	如何为特定语言/场景提供开箱即用的安全执行能力？
Layer 2	沙箱平台服务	如何大规模地创建、管理、调度隔离环境？
Layer 3	专项沙箱	如何为特定交互目标（浏览器、MCP、桌面）提供沙箱？
Layer 4	Agent 市场与编排	如何将沙箱 + 能力打包为可复用、可交易的 Agent 产品？
层级依赖关系示例：
Manus (应用) → E2B (Layer 2) → Firecracker (Layer 0)
K8s Agent Sandbox (Layer 2) → gVisor / Kata Containers (Layer 0)
MCP Jail (Layer 3) → Docker + seccomp (Layer 0)
Vercel Sandbox (Layer 2) → Firecracker (Layer 0)
Modal Sandbox (Layer 2) → gVisor (Layer 0)
Firecrawl Browser Sandbox (Layer 3) → 容器隔离 (Layer 0)
Anthropic srt (Layer 3) → Bubblewrap / sandbox-exec (Layer 0)

4. Layer 0：隔离原语
隔离原语是整个沙箱生态的技术地基。它们决定了安全边界的强度、性能开销和可用功能。
4.1 技术全景
当前 Agent 沙箱领域的隔离原语可分为 4 大类：
类别	技术	隔离强度	启动速度	内存开销	典型使用者
硬件虚拟化（microVM）	Firecracker	★★★★★	~125ms	~5MB	E2B, Vercel, Sprites, Deno
	Kata Containers	★★★★★	~1-2s	~20-30MB	K8s Agent Sandbox, Northflank
	Cloud Hypervisor	★★★★★	~150ms	~10MB	部分云厂商内部
用户态内核	gVisor (runsc)	★★★★	~数百ms	~15-20MB	Modal, K8s Agent Sandbox, OpenSandbox
OS 级沙箱	Bubblewrap + seccomp	★★★	<10ms	~0	Anthropic srt
	Landlock + seccomp	★★★	<10ms	~0	OpenAI Codex
	Linux namespaces/cgroups	★★	<50ms	~0	Docker（基础）
语言级沙箱	WASM/WASI	★★★	<1ms	~1-2MB	MCP-SandboxScan, Asterbot
	Deno (V8)	★★★	<10ms	~5MB	LangChain Sandbox
	Pyodide	★★	~1-2s	~20MB	浏览器端执行
4.2 Firecracker
概述：AWS 开源的 microVM 管理器（VMM），用 Rust 编写，代码量仅约 50,000 行（QEMU 约 200 万行 C 代码）。最初为 AWS Lambda 和 Fargate 构建，现已成为 AI Agent 沙箱领域的事实标准。
架构原理：
● 基于 Linux KVM 虚拟化，每个 microVM 拥有独立内核、内存空间和文件系统
● 通过 VirtIO 设备提供网络和块存储，最小化设备模型以减少攻击面
● 每个实例仅需约 5MB 内存，启动时间约 125ms
优点：
● 硬件级隔离，安全边界最强，内核漏洞无法跨 VM 传播
● 极低内存开销，单台服务器可运行数千实例
● 快速启动，满足 Agent 交互式场景的延迟要求
● 成熟的生产经验（AWS Lambda/Fargate 级别验证）
● 完整的 Linux 环境，Agent 可以安装包、修改系统文件、运行任意二进制
缺点：
● 需要裸金属服务器或支持嵌套虚拟化的环境（不能在普通 VM 中嵌套运行）
● 仅支持 Linux（macOS/Windows 不原生支持）
● 不支持 GPU 直通（需要额外的 VFIO 配置，实践中较复杂）
● 网络配置比容器复杂
开源状态：Apache 2.0，github.com/firecracker-microvm/firecracker，活跃维护。
4.3 gVisor (runsc)
概述：Google 开源的用户态内核，通过在用户空间拦截和重新实现 Linux 系统调用来提供隔离，介于容器和 VM 之间。
架构原理：
● gVisor 的 Sentry 组件作为 guest kernel 运行在用户空间，拦截应用的所有系统调用
● 应用的系统调用由 Sentry 在用户态处理，仅在必要时通过 Gofer 进程代理到 host kernel
● 拦截 200+ Linux 系统调用，减少了约 70% 的 host kernel 攻击面
优点：
● 无需硬件虚拟化支持，可在任何 Linux 环境（包括 VM 内）运行
● 兼容 OCI 容器标准，可与 Docker/Kubernetes 无缝集成
● 比 microVM 更轻量的资源开销
● 不需要嵌套虚拟化
缺点：
● 非所有系统调用都被完整实现，少数应用可能有兼容性问题
● 性能开销高于原生容器（系统调用拦截带来 5-30% 的 overhead）
● 隔离强度弱于 microVM（共享 host kernel，虽然攻击面大幅缩小）
● 对 I/O 密集型工作负载性能影响更明显
开源状态：Apache 2.0，github.com/google/gvisor，Google 主导维护。
4.4 Kata Containers
概述：OpenInfra Foundation 旗下项目，将轻量 VM 封装为 OCI 兼容的容器运行时。结合了 VM 级隔离和容器的使用体验。
架构原理：
● 每个容器/Pod 运行在独立的轻量 VM 中
● 支持多种 hypervisor 后端：QEMU、Firecracker、Cloud Hypervisor
● 通过 containerd-shim-kata-v2 与 Kubernetes 生态无缝对接
优点：
● Kubernetes 原生集成，对现有编排基础设施零侵入
● 支持多种 hypervisor，可根据需求选择性能/隔离平衡点
● 生产验证：每月处理超过 200 万隔离工作负载
● 与 K8s Agent Sandbox CRD 原生集成
缺点：
● 启动时间较 Firecracker 直接使用更长（1-2 秒）
● 内存开销高于 Firecracker（~20-30MB per instance）
● 配置和运维复杂度高于 gVisor
● WASM 支持（通过 Wasmer 集成）仍在早期阶段
开源状态：Apache 2.0，github.com/kata-containers/kata-containers。
4.5 WASM/WASI
概述：WebAssembly 作为一种字节码格式，天然具备沙箱特性——线性内存隔离、能力模型安全、平台无关。WASI（WebAssembly System Interface）为其提供标准化的操作系统接口。
架构原理：
● 每个 WASM 实例拥有独立的线性内存空间，内存访问有边界检查
● WASI 0.2 基于 Component Model，每个组件只能通过 WIT 接口定义的类型化通道交换数据
● Capability-based security：模块启动时零权限，所有能力需显式授予
优点：
● 微秒级冷启动（比 Firecracker 快 3 个数量级）
● 天然的内存安全和沙箱隔离
● 平台无关，同一模块可在服务端、浏览器、边缘运行
● 极低内存开销（~1-2MB per instance）
● Component Model 支持模块化组合，适合构建可插拔的 Agent 能力
缺点：
● 无法提供完整的 Linux 环境（不能 apt install、不能运行任意二进制）
● WASI 生态仍在成熟中（WASI 0.3 的 async I/O 尚未稳定）
● 语言支持有限（Rust、C/C++ 一等支持，Python 需要 Pyodide 编译）
● 不适合需要完整 OS 语义的场景（文件系统、网络、进程管理）
主要运行时：Wasmtime（Bytecode Alliance）、WasmEdge（CNCF）、Wasmer。
适用场景：计算密集型、无状态的工具执行；作为 Defense-in-depth 的一层（WASM-in-Container）；浏览器端代码执行。
4.6 OS 级沙箱（Bubblewrap / seccomp / Landlock）
概述：直接利用 Linux 内核的安全原语实现进程级隔离，无需虚拟化或容器运行时。
Bubblewrap（Anthropic srt 使用）：
● 利用 Linux user namespaces 创建受限的进程环境
● 可控制文件系统挂载、网络访问、进程可见性
● 配合 seccomp-bpf 过滤系统调用
● Anthropic 的 srt 工具额外增加了代理 (proxy) 层来精细控制网络出站
Landlock + seccomp（OpenAI Codex 使用）：
● Landlock 是 Linux 5.13+ 的内核安全模块，提供非特权进程的文件系统沙箱
● 与 seccomp-bpf 配合，限制系统调用和文件系统访问
● 无需 root 权限或容器运行时
优点：
● 零额外资源开销（直接利用内核能力）
● 亚毫秒级启动
● 无需容器/VM 基础设施
● 适合开发者本地环境（macOS 可用 sandbox-exec，Linux 可用 bubblewrap）
缺点：
● 隔离强度依赖于内核配置，不如 microVM 的硬件隔离
● 共享 host kernel，内核漏洞直接影响沙箱
● 跨平台一致性差（Linux/macOS 机制完全不同）
● 配置复杂，策略编写容易遗漏

5. Layer 1：沙箱运行时与 SDK
Layer 1 在隔离原语之上提供开发者友好的封装——SDK、API、CLI——让 Agent 框架可以直接调用沙箱能力，而不需要自己处理底层隔离细节。
5.1 Ouros
定位：用 Rust 编写的沙箱 Python 运行时，追求极致启动速度。
技术特点：
● 亚微秒级启动时间（比传统 Python 进程快 6 个数量级）
● 持久 REPL 会话，支持执行快照和恢复
● 类型检查、72 个标准库模块
● 资源限制：内存、分配次数、栈深度、执行时间
● 多语言绑定：Python、JavaScript/TypeScript、Rust
隔离机制：语言级沙箱（不使用容器或 VM），通过限制可用模块和资源配额实现安全。
优点：启动极快，资源占用极低，适合高频、短时的代码执行场景。
缺点：仅支持 Python 子集（72 个 stdlib 模块），无法运行任意系统命令。
开源：MIT，github.com/parcadei/ouros。
5.2 Enclave
定位：面向 AI Agent 的安全 JavaScript 沙箱，TypeScript-first 设计。
技术特点：
● 6 层安全保护：AST 验证 → 作用域隔离 → 原型冻结 → 运行时监控 → 资源限制 → 输出过滤
● 防御代码注入、原型链污染、沙箱逃逸
● 支持流式运行时和 tool 调用
隔离机制：语言级沙箱（V8 isolate + AST 级代码审查）。
优点：专为 JS/TS 生态设计，集成简单，防护全面。
缺点：仅限 JavaScript/TypeScript，依赖 V8 引擎安全性。
开源：Apache 2.0，github.com/agentfront/enclave。
5.3 Agent Tool Sandbox
定位：策略驱动的 Agent 工具执行沙箱，提供 REST API。
技术特点：
● 基于 FastAPI 的 REST 接口
● 策略引擎：可配置网络/文件系统隔离规则
● 执行历史追踪
● OpenTelemetry 审计日志
隔离机制：容器 + 策略引擎（底层依赖 Docker）。
优点：策略可编程，审计能力强，适合企业合规场景。
缺点：依赖 Docker，隔离强度取决于容器配置。
开源：github.com/airblackbox/agent-tool-sandbox（2026.02）。
5.4 NanoClaw
定位：轻量级 AI Agent 框架，集成 Docker Sandbox 隔离。
技术特点：
● 单进程 Node.js 架构，15 个核心源文件，约 3,900 行代码
● 每个群组独立容器、独立文件系统、独立 CLAUDE.md 记忆
● Agent Swarm 协作模式
● 多渠道：WhatsApp（内置）、Telegram、Discord、Slack
● Docker Sandbox 集成（2026.03）：容器 + microVM 双层隔离
隔离机制：Docker 容器（Apple Container on macOS），可选 Docker Sandbox microVM。
优点：极简架构易于审计（100x smaller than alternatives），多渠道开箱即用。
缺点：功能相对基础，并发容器限制（默认 3），microVM 支持依赖 Docker Desktop。
开源：MIT，23.4k+ GitHub stars（2026.03）。
5.5 LangChain Deep Agents
定位：LangChain 官方的结构化 Agent 运行时，基于 LangGraph 构建。
技术特点：
● 规划工具（write_todos）、文件系统操作（read_file、write_file、edit_file）
● 沙箱化 Shell 访问（execute）
● 子 Agent 生成和上下文管理
● 内存和上下文隔离
隔离机制：依赖外部沙箱（推荐使用 E2B 或其他 Layer 2 服务）。
注意：LangChain 的 langchain-sandbox 包已于 2026 年归档，官方推荐使用专用沙箱 API。这反映了一个趋势：Agent 框架层倾向于不自建沙箱，而是对接专业沙箱服务。
5.6 Layer 1 对比表
项目	语言支持	隔离层	启动速度	开源协议	定位
Ouros	Python（子集）	语言级（Rust 进程内）	<1μs	MIT	高频轻量执行
Enclave	JS/TS	语言级（V8 isolate）	<10ms	Apache 2.0	JS Agent 安全执行
Agent Tool Sandbox	多语言（通过 Docker）	容器 + 策略	~1-2s	OSS	企业审计合规
NanoClaw	通过 Shell	容器 / microVM	~1-2s	MIT	个人 Agent 助手
LangChain Deep Agents	Python	外部沙箱	取决于后端	MIT	Agent 编排运行时

6. Layer 2：沙箱平台服务
Layer 2 是整个生态的核心竞争层——提供大规模、可管理、API 驱动的沙箱创建和调度能力。这一层的产品直接面向 Agent 开发者和 AI 产品公司。
6.1 E2B
定位：AI Agent 云，专注于临时（ephemeral）沙箱。目前最成熟、市场份额最大的 Agent 沙箱平台。
技术架构：
● 底层隔离：Firecracker microVM
● 冷启动：~150ms
● 会话最长 24 小时，到期自动销毁
● SDK：Python、JavaScript/TypeScript
● 自托管部署：支持客户在自有基础设施运行 E2B 集群
规模与采用：
● 200M+ 沙箱启动量
● 88% 的 Fortune 100 企业使用
● 关键客户：Hugging Face、Perplexity、Groq、Manus
● 七位数 MRR（2025 年）
● 融资：$21M Series A（2025.07，Insight Partners 领投）
定价模型：
● 按使用量计费
● 免费额度 + 阶梯定价
优点：
● 生态最成熟，SDK 质量高
● 启动速度快，适合交互式 Agent
● 企业验证充分
● 开源核心（可自托管）
缺点：
● 仅限临时沙箱（24h 上限），不适合长时间运行的工作负载
● 不支持 GPU
● 持久化能力有限（需外部存储）
● 托管版锁定在 E2B 的基础设施上
开源状态：开源，github.com/e2b-dev/E2B。
上层使用者：Manus（自托管 E2B → Firecracker）。
6.2 Daytona
定位："给每个 Agent 一台计算机"——强调持久化状态和 Computer Use 能力。
技术架构：
● 底层隔离：Docker 容器（不是 microVM）
● 创建速度：90ms（业界最快）
● 支持持久化状态和沙箱恢复（Restore）
● Computer Use：鼠标、键盘、截屏、录屏
● SDK：Python
规模与采用：
● $1M forward revenue in <3 months（2026 年初）
● 关键客户：LangChain、Turing、Writer、SambaNova
● 融资：$24M Series A（2026.02，FirstMark Capital 领投，Datadog 和 Figma 战略投资）
优点：
● 创建速度最快（90ms）
● 内置 Computer Use 能力
● 持久化状态，适合长时间运行的 Agent
● 快速增长的客户基础
缺点：
● Docker 隔离强度弱于 microVM（共享内核）
● Computer Use 目前仅支持 Linux（Windows/macOS Private Alpha）
● 相比 E2B，生态成熟度较低
6.3 Sprites（Fly.io）
定位：有状态的 Agent 沙箱，主打 Checkpoint/Restore 能力。
技术架构：
● 底层隔离：Firecracker microVM
● 创建时间：1-2 秒
● Checkpoint/Restore：~1 秒，完整文件系统状态快照
● 持久化存储（对象存储支持）
● 空闲时不计费
定价：$0.07/CPU-hour，$0.04375/GB-hour，idle 免费。
优点：
● Checkpoint/Restore 是杀手级特性——可以在风险操作前保存状态，失败后快速回滚
● microVM 级隔离（安全性优于 Daytona 的 Docker）
● 按需计费，空闲时零成本
● 背靠 Fly.io 的全球基础设施
缺点：
● 创建速度慢于 E2B 和 Daytona
● SDK/生态不如 E2B 成熟
● 文档和社区相对较小
6.4 Modal
定位：AI 基础设施平台，沙箱是其产品矩阵的一部分。
技术架构：
● 底层隔离：gVisor (runsc)
● 冷启动：~2 秒
● 强大的 GPU 支持
● SDK：Python、JavaScript、Go
● 无缝 GPU 工作负载调度
优点：
● 唯一在沙箱级别提供强 GPU 支持的平台
● gVisor 隔离不需要裸金属，部署灵活
● 一站式 AI 基础设施（计算、存储、调度、沙箱）
缺点：
● 冷启动最慢（~2s）
● 沙箱不是核心产品，功能迭代可能不如专注型公司快
● gVisor 隔离强度弱于 Firecracker
6.5 Vercel Sandbox
定位：为 AI Agent 和 v0 等产品提供代码执行环境。
技术架构：
● 底层隔离：Firecracker microVM，构建在内部平台 "Hive" 之上
● 基础镜像：Amazon Linux 2023（预装 Node.js、Python）
● 毫秒级启动
● 快照能力：可以快速恢复复杂环境
● SDK：@vercel/sandbox npm 包
● 日均 270 万次部署
优点：
● 与 Vercel 生态深度集成
● Firecracker 级隔离安全性
● 快照恢复能力
● 规模验证充分
缺点：
● 强绑定 Vercel 生态
● 主要面向 Web 开发场景
● 定价与 Vercel 整体计费耦合
开源状态：SDK 开源（github.com/vercel/sandbox），底层基础设施闭源。
6.6 Deno Sandbox
定位：在 Deno Deploy 上提供即时 Linux microVM。
技术架构：
● 底层隔离：Linux microVM
● 亚秒级启动
● 持久化存储：Volumes（300MB - 20GB），支持快照
● 网络策略：allowlist 控制
● SDK：Node.js、Deno、Python
优点：
● 持久化文件系统（Volumes + Snapshots）
● 精细网络控制（allowlist）
● 安全的 secret 隔离（只向批准目标暴露值）
缺点：
● 与 Deno Deploy 绑定
● Volume 上限 20GB
● 生态规模较小
6.7 OpenSandbox（阿里巴巴）
定位：通用沙箱平台，面向 coding agent、GUI agent、Agent 评估和 RL 训练。
技术架构：
● 底层隔离：gVisor（默认），可选 Kata Containers 或 Firecracker
● 冷启动：<800ms
● 多语言 SDK：Python、TypeScript、Go、Java、C#/.NET（Rust 在 roadmap）
● Docker 和 Kubernetes 部署支持
● 资源限制：CPU、内存、磁盘、网络/文件系统访问控制
规模与采用：
● 7,927 GitHub stars（2026.03 中旬）
● 首 72 小时获得 3,845 stars
● 40 位贡献者，57 个版本发布
● 发布时间：2026.03.03（非常新）
优点：
● 隔离后端可选（gVisor/Kata/Firecracker），灵活度最高
● SDK 覆盖最广（6 种语言）
● 完全可自托管，无供应商锁定
● Apache 2.0 许可，真正的开源
● 支持 GUI Agent 场景
缺点：
● 非常新（2026.03 刚发布），生产验证不足
● 缺少托管服务（SaaS），需要自建基础设施
● 文档和社区仍在建设中
6.8 Kubernetes Agent Sandbox
定位：Kubernetes 原生的 Agent 沙箱编排框架，由 Google 主导。
技术架构：
● Kubernetes SIG Apps 子项目
● 自定义资源（CRD）：Sandbox、SandboxTemplate、SandboxClaim、SandboxWarmPool
● 底层隔离：gVisor（默认）或 Kata Containers
● Python SDK
● 预热池（WarmPool）机制减少启动延迟
规模与采用：
● 1,225 GitHub stars
● v0.2.1（2026.03）
● GKE 原生集成，也可在 EKS/AKS 部署
优点：
● Kubernetes 原生，适合已有 K8s 基础设施的企业
● WarmPool 预热机制有效降低延迟
● Google 主导，长期维护有保障
● 支持万级并发沙箱
缺点：
● 依赖 Kubernetes（门槛高，不适合小团队）
● 仍在早期阶段（v0.2.x）
● 不提供托管服务，需自建 K8s 集群
● 缺少 Computer Use 等高级特性
6.9 Northflank
定位：企业级沙箱平台，支持多种隔离后端。
技术架构：
● 隔离后端：Kata Containers / Firecracker（microVM）或 gVisor
● 亚秒级冷启动
● 临时或持久化沙箱
● Volume 支持（4GB - 64TB）
● GPU 支持（L4、A100、H100、H200）
● 部署方式：托管或 BYOC（自有 VPC）
定价：
● 通用计算：$2.70/月起（0.1 vCPU + 256MB）
● GPU：$0.80/h（L4）至$3.14/h（H200）
优点：
● 无会话时长限制（vs E2B 的 24h）
● GPU 支持全面
● BYOC 部署满足企业安全要求
● 灵活的隔离后端选择
缺点：
● 闭源商业产品
● 品牌知名度低于 E2B
● 定价相对较高
6.10 Layer 2 对比表
平台	隔离原语	创建速度	持久化	GPU	Computer Use	开源	自托管	定价模式
E2B	Firecracker	~150ms	否（24h 上限）	否	否	是	是	按量
Daytona	Docker	90ms	是	否	是	否	否	按量
Sprites	Firecracker	~1-2s	是（Checkpoint）	否	否	否	否	按量（idle 免费）
Modal	gVisor	~2s	否	是	否	否	否	按量
Vercel	Firecracker	<1s	是（Snapshot）	否	否	SDK 开源	否	与 Vercel 计费耦合
Deno	microVM	<1s	是（Volume）	否	否	否	否	按量
OpenSandbox	gVisor/Kata/FC	<800ms	是	否	是（GUI）	是 (Apache 2.0)	是	免费（自托管）
K8s Agent Sandbox	gVisor/Kata	依赖 WarmPool	是	否	否	是	仅自托管	免费（自建）
Northflank	Kata/FC/gVisor	<1s	是	是	否	否	BYOC	按量

7. Layer 3：专项沙箱
Layer 3 为特定交互目标提供专门的沙箱能力：浏览器自动化、MCP 工具隔离、桌面操作（Computer Use）。
7.1 MCP 工具沙箱
MCP（Model Context Protocol）server 是 AI Agent 调用外部工具的主流接口。但安全审计显示：96.4% 的 MCP server 存在可利用漏洞，70.3% 可执行任意 shell 命令，75.4% 可以向远程服务器泄露数据。
7.1.1 MCP Jail
定位：给 MCP server 套上沙箱外壳。
工作原理：在 MCP server 启动命令前加 mcpjail 前缀，将整个 server 进程包裹在强化 Docker 容器中。
隔离措施：
● 丢弃 Linux capabilities
● 只读文件系统
● 无网络访问
● 自动清理
● CPU/内存/PID 限制
优点：即插即用，不需修改 MCP server 代码。
缺点：依赖 Docker，粒度只到整个 server（无法按工具隔离）。
7.1.2 e2b-mcp
定位：在 E2B 云沙箱中运行 MCP server。
工作原理：每个 MCP server 运行在独立的 E2B Firecracker microVM 中，通过 CLI 或 Python API 管理。
优点：Firecracker 级隔离，托管式无需运维。
缺点：需要网络往返（MCP server 在云端），增加延迟。
7.1.3 MCP-SandboxScan
定位：基于 WASM 的 MCP 工具安全分析框架。
工作原理：在 WASM/WASI 沙箱中执行不受信任的 MCP 工具，同时分析运行时行为。检测 prompt/message/tool_return 中的外部输入到 sink 的暴露路径，捕获文件系统 capability 违规。
优点：WASM 提供细粒度隔离，可做运行时行为分析。
缺点：研究性项目，不是成熟产品。
7.1.4 Code Sandbox MCP Server
定位：在 Docker/Podman 容器中执行 Python/JavaScript 代码片段的 MCP server。
工作原理：每次代码执行启动一个容器实例，可配置容器镜像和环境变量。
优点：简单直接，开箱即用。
缺点：容器级隔离（共享内核），每次执行启动容器有延迟。
7.2 浏览器沙箱
AI Agent 操作网页需要真实的浏览器环境，但在本地运行浏览器存在安全和资源问题。云端浏览器沙箱解决了这个问题。
7.2.1 Browserbase
定位：为 AI Agent 和应用提供无头浏览器基础设施。
技术特点：
● Chrome DevTools Protocol (CDP) 集成
● 兼容 Playwright、Puppeteer、Selenium + 自有框架 Stagehand
● SOC-2 Type 1 和 HIPAA 合规
● Session recording
● 反检测（Stealth）能力
● 认证持久化（Contexts）
优点：合规认证最全，反检测能力强，生态兼容性最好。
缺点：闭源商业产品，定价不透明。
7.2.2 Steel
定位：云端浏览器基础设施，集成 Browser-Use 开源库。
技术特点：
● 与 Browser-Use（开源 AI 网页自动化库）深度集成
● Profile persistence：跨 session 保持认证状态
● 最佳配合 vision-capable 模型（GPT-4o、Claude 3）
优点：与开源 Browser-Use 生态紧密结合。
缺点：需要 Python 3.11+，依赖 vision model。
7.2.3 Firecrawl Browser Sandbox
定位：零配置的远程浏览器环境。
技术特点：
● 预装 Chromium + Playwright + Agent Browser
● 持久化或临时 session
● 兼容 Claude Code 等 Agent
● 基于信用点（credit）计费：2 credits/min
优点：零配置，一行命令启动，多 Agent 兼容。
缺点：credit 计费可能成本较高。
7.3 Computer Use 沙箱
Computer Use 是 2025-2026 年最热的 Agent 能力方向——让 Agent 像人一样操作桌面应用。
7.3.1 Daytona Computer Use
能力：鼠标操作、键盘输入、截屏、录屏。
支持 OS：Linux（GA），Windows/macOS（Private Alpha）。
与 Layer 2 集成：Daytona 的 Computer Use 直接运行在其沙箱内。
7.3.2 OpenSandbox GUI Agent
能力：GUI 交互环境，支持桌面应用操作。
隔离：gVisor/Kata/Firecracker 级隔离。
优势：开源，可自托管。
7.4 轻量级进程沙箱
7.4.1 Anthropic srt（sandbox-runtime）
定位：Anthropic 开源的轻量级 CLI 工具，用于沙箱化 Agent、MCP server 和任意进程。
技术：
● macOS：sandbox-exec（系统原生）
● Linux：Bubblewrap + proxy
● 不需要 Docker 或 VM
● 文件系统限制 + 网络代理过滤
优点：最轻量，开发者本地环境即可使用，无基础设施依赖。
缺点：隔离强度有限，不适合多租户生产环境。
7.4.2 Matchlock
定位：在 microVM 中运行 AI Agent，带 secret 注入和网络 allowlist。
技术特点：
● Go 编写
● 临时 Firecracker microVM，亚秒级启动
● 网络 allowlist
● MITM proxy 注入 secret（secret 永远不进入 VM）
● 支持 Linux（KVM）和 macOS（Apple Silicon）
优点：secret 管理设计独特（MITM proxy），安全性考虑深入。
缺点：工具型 CLI，不是平台服务。
7.5 Layer 3 对比表
产品	子类别	隔离层	核心特性	开源
MCP Jail	MCP 沙箱	Docker + seccomp	即插即用，无需改代码	是
e2b-mcp	MCP 沙箱	Firecracker（E2B）	云端隔离	是
MCP-SandboxScan	MCP 沙箱	WASM/WASI	运行时行为分析	是
Code Sandbox MCP	MCP 沙箱	Docker/Podman	简单代码执行	是
Browserbase	浏览器	容器	合规认证，反检测	否
Steel	浏览器	容器	Browser-Use 集成	否
Firecrawl Browser	浏览器	容器	零配置，多 Agent 兼容	否
Anthropic srt	进程沙箱	OS 原语	最轻量，本地可用	是
Matchlock	进程沙箱	Firecracker	Secret 注入，网络控制	是

8. Layer 4：Agent 市场与编排平台
Layer 4 是整个技术栈的最上层——将沙箱能力封装为可发现、可部署、可交易的 Agent 产品。这也是你关注的 "sandbox + skills = 垂直 Agent 市场" 的方向。
8.1 现有玩家
8.1.1 OnlyVercel
定位：开发者在 Vercel 基础设施上发布和部署 AI Agent 的开放市场。
数据：20 个 Agent、119.4K 总部署、90% 开发者分成。
基础设施：沙箱、自动扩缩、AI Gateway、可观测性。
模式：Agent 开发者发布 → 用户一键部署到自己的 Vercel 账号。
8.1.2 AgentDeploy
定位：一键部署 AI Agent，支持多云（Railway、Vultr、Render 等）。
特点：
● 私有 GitHub 中间件
● 加密凭证保险库
● 70% 模板创作者分成
8.1.3 AgentSphere
定位：AI 原生云基础设施 + MCP 集成沙箱。
特点：
● 数据分析和可视化
● 浏览器自动化
● 有状态多阶段工作流
● LLM 评估
8.1.4 Jenova
定位：统一的 AI Agent 市场，提供专业 Agent 访问。
特点：
● 多模型支持（GPT-5.2、Claude Opus 4.5 等）
● 自定义知识库
● 工具集成
8.2 Layer 4 的关键观察
1. 碎片化严重：没有一个平台同时做到了 "强沙箱隔离 + 丰富 skills 生态 + 开放市场"。
2. 偏应用层：现有市场平台更关注 Agent 的发布和部署，而不是底层沙箱的安全和隔离。
3. 缺少 skills 组合能力：现有平台是 "部署一个完整 Agent"，而不是 "组合 sandbox + skills 形成垂直 Agent"。
4. 开源空白：Layer 4 几乎没有开源项目，全部是闭源 SaaS。

9. 全景对比矩阵
9.1 隔离技术对比
维度	Firecracker	gVisor	Kata	WASM/WASI	Bubblewrap/seccomp	Docker（原生）
隔离强度	★★★★★	★★★★	★★★★★	★★★	★★★	★★
启动速度	~125ms	~数百ms	~1-2s	<1ms	<10ms	~500ms
内存开销	~5MB	~15-20MB	~20-30MB	~1-2MB	~0	~10MB
完整 Linux 环境	是	是	是	否	部分	是
GPU 支持	困难	部分	部分	否	N/A	是
嵌套虚拟化要求	是	否	是	否	否	否
K8s 集成	间接	原生	原生	间接	否	原生
主要用途	Agent 沙箱主流	灵活备选	企业 K8s	轻量计算	开发者本地	开发测试
9.2 平台服务对比
维度	E2B	Daytona	Sprites	Modal	Vercel	OpenSandbox	K8s AgentSandbox
隔离原语	Firecracker	Docker	Firecracker	gVisor	Firecracker	gVisor+	gVisor/Kata
创建速度	~150ms	90ms	~1-2s	~2s	<1s	<800ms	依赖 WarmPool
持久化	否	是	是(Checkpoint)	否	是(Snapshot)	是	是
GPU	否	否	否	是	否	否	否
Computer Use	否	是	否	否	否	是(GUI)	否
开源	是	否	否	否	SDK	是	是
自托管	是	否	否	否	否	是	是
成熟度	高	中	中	高	高	低(新)	低(v0.2)
融资	$21M	$24M	(Fly.io)	(独角兽)	(Vercel)	(阿里巴巴)	(Google)

10. 技术趋势与演进方向
10.1 Checkpoint/Restore 成为标配
Sprites 首先将 Checkpoint/Restore 作为核心特性推出——在任意时刻快照沙箱的完整状态，并在亚秒级恢复。这一能力对 Agent 至关重要：
● 容错：在执行风险操作前保存检查点，失败后回滚
● 分支探索：从同一个检查点出发尝试多种策略
● 成本优化：暂停闲置沙箱，需要时快速恢复
● 协作：共享已知良好的环境状态
Daytona（Restore）、Vercel（Snapshot）也已跟进。预计 2027 年，Checkpoint/Restore 将成为所有沙箱平台的标配功能。
10.2 Computer Use 快速普及
2025 年 Anthropic Claude 推动了 Computer Use 概念的普及——Agent 不仅运行代码，还能像人一样操作桌面应用（鼠标点击、键盘输入、截屏分析）。
当前状态：
● Daytona：已 GA（Linux），Windows/macOS Private Alpha
● OpenSandbox：GUI Agent 支持
● 浏览器沙箱（Browserbase、Steel、Firecrawl）：Web 层面的 Computer Use
趋势预判：2028 年前，Computer Use 将成为沙箱平台的标准功能（而非差异化特性）。
10.3 WASM 的潜力与局限
WASM 在 AI Agent 沙箱领域展现出独特价值：
已验证的场景：
● MCP 工具安全分析（MCP-SandboxScan）
● 模块化 Agent 组件（Asterbot：可热插拔的 WASM Agent 组件）
● 轻量级计算隔离（Defense-in-depth 的内层）
演进路线：
● WASI 0.2（2024）：Component Model + capability-based security
● WASI 0.3（预计 2025-2026）：原生 async I/O
● WASI 1.0（时间待定）：稳定版
预判：WASM 不会取代 Firecracker/gVisor 成为主流 Agent 沙箱隔离层，但会在以下场景占据一席之地——(1) 轻量级工具/skill 执行；(2) 浏览器端代码运行；(3) 作为 Defense-in-depth 的额外层。
10.4 临时 vs 持久化的融合
早期的 Agent 沙箱设计是明确的二选一：
● 临时派（E2B）：每次会话创建新沙箱，24h 后销毁
● 持久派（Daytona、Sprites）：沙箱可以持续运行，保存状态
趋势是走向融合——通过 Checkpoint/Restore 机制，一个沙箱可以在 "临时运行 + 按需持久化" 之间灵活切换。
10.5 Agent 框架不再自建沙箱
LangChain 归档 langchain-sandbox、推荐使用专用沙箱 API 是一个信号：Agent 框架层（LangChain、CrewAI、AutoGen 等）正在放弃自建沙箱，转而对接专业的沙箱平台。
这意味着 Layer 2 的沙箱平台将享受到 Agent 框架增长的红利——每个新 Agent 框架的用户都需要一个沙箱服务。
10.6 Defense-in-Depth 成为最佳实践
单一隔离层已不被视为足够安全。最佳实践是多层组合：
外层: Firecracker microVM (硬件隔离)
  ├─ 中层: gVisor / seccomp (系统调用过滤)
  │   └─ 内层: WASM (语言级隔离)
  └─ 侧面: 网络策略 + 文件系统限制 + 资源配额

11. 机会分析
11.1 你的核心洞察
Sandbox + Skills = 垂直 Agent → 垂直 Agent Market
这个等式揭示了当前生态的一个结构性空白：
● Layer 0-2（隔离 → 平台）已经有成熟的竞争者，且资金充沛（E2B $21M、Daytona$24M）。直接做另一个沙箱平台没有明显优势。
● Layer 4（Agent 市场）虽然存在几个早期玩家，但它们要么是闭源 SaaS、要么与特定基础设施强绑定（OnlyVercel ↔ Vercel）、要么缺少沙箱隔离能力。
● 没有人在 Layer 2 和 Layer 4 之间架起一座桥——一个开放的、以 sandbox + skills 为组合单元的垂直 Agent 市场。
11.2 空白地带详解
空白 1：开放的 Agent 组合层
当前的 Agent 市场是 "部署一个完整 Agent" 模式——Agent 是黑盒，用户只能用或不用。
缺少的是一个 组合层：用户/开发者可以选择一个 sandbox 环境模板 + 一组 skills，组合出一个特定领域的 Agent。例如：
● Python 数据分析沙箱 + pandas/matplotlib skills + CSV 上传工具 = 数据分析 Agent
● Node.js Web 开发沙箱 + React/Next.js skills + Vercel 部署工具 = 前端开发 Agent
● Linux 全功能沙箱 + kubectl/helm skills + K8s API 工具 = DevOps Agent
空白 2：跨沙箱平台的统一抽象
开发者目前需要选择一个沙箱平台（E2B 或 Daytona 或 Modal），然后被锁定在该平台的 SDK 和定价模型中。
一个中间抽象层可以：
● 统一 E2B/Daytona/OpenSandbox/K8s Agent Sandbox 的 API
● 让 skills 和 sandbox 模板在不同后端之间可移植
● 允许用户根据需求（成本、GPU、持久化、隔离强度）自动选择最佳后端
空白 3：Skills 市场的沙箱安全保证
当前的 MCP 工具生态存在严重安全问题（96.4% 有漏洞）。如果要构建一个 skills 市场，每个 skill 需要在沙箱中运行并通过安全审计。
这可以成为差异化壁垒：不只是一个 skills 列表，而是每个 skill 都有 沙箱执行保证 + 安全审计报告 + capability 声明（受 WASM capability model 启发）。
空白 4：开源 Layer 4
整个 Layer 4 几乎没有开源项目。一个开源的 Agent 市场框架，让任何人可以自托管一个垂直 Agent 市场（面向特定行业或场景），是一个明确的空白。
11.3 潜在切入路径
路径 A：Sandbox-as-a-Skill + Agent Marketplace（推荐）
构建一个开源平台，核心概念：
1. Sandbox Template：预配置的沙箱环境（Python 数据科学、Node.js Web 开发、Linux DevOps…）
2. Skill Pack：一组工具/能力定义（MCP server、函数、prompt）
3. Agent = Sandbox Template + Skill Pack：组合产出一个垂直 Agent
4. Marketplace：开发者发布 Sandbox Template 和 Skill Pack，用户自由组合
技术栈建议：
● 底层对接：E2B（开源，可自托管）或 OpenSandbox（开源，多后端）
● Skill 格式：兼容 MCP + 自定义扩展
● Agent 定义：声明式 YAML/TOML（sandbox template + skills + config）
● 市场前端：开源 Web UI，支持搜索、评分、组合预览
与 bub 的关系：bub 已有 skills 系统和插件架构，可以作为这个平台的 Agent 运行时之一。
路径 B：Sandbox Orchestration Layer
做一个跨沙箱平台的统一抽象层（类似于 Terraform 之于云厂商）：
1. 统一 API 抽象 E2B/Daytona/OpenSandbox/K8s Agent Sandbox
2. 声明式配置：开发者描述需求（隔离强度、GPU、持久化），平台自动选择后端
3. 成本优化：根据用量模式自动在不同后端之间迁移
风险：需要适配多个上游平台的 API 变化，维护成本高。
路径 C：Secure Skills Registry
专注于做一个安全的 skills 注册和分发平台：
1. 每个 skill 必须声明 capability 需求（文件系统、网络、系统调用…）
2. 自动化安全审计（静态分析 + WASM 沙箱动态检测）
3. 沙箱执行保证：skill 只在声明的 capability 范围内运行
4. 与现有 Agent 框架集成（MCP 兼容）
优势：切口小，聚焦安全差异化，与 MCP 生态趋势一致。
风险：需要达到临界规模才有网络效应。
11.4 竞争壁垒分析
壁垒类型	路径 A	路径 B	路径 C
网络效应（双边市场）	★★★★★	★★	★★★★
技术门槛	★★★	★★★★	★★★
生态锁定	★★★★	★★	★★★
开源社区	★★★★	★★★	★★★★
与 bub 协同	★★★★★	★★	★★★
11.5 建议
首选路径 A，原因：
1. 最大的市场空白：Layer 4 的开源空间完全空白
2. 网络效应最强：双边市场（skill 开发者 ↔ Agent 用户）一旦建立，壁垒极高
3. 与 bub 深度协同：bub 的 skills 系统、hook 架构、多渠道支持可以直接作为 Agent 运行时
4. 渐进可行：可以从 bub 的 skills 生态开始（冷启动），逐步开放为通用市场
MVP 建议：
1. 定义 Sandbox Template 和 Skill Pack 的声明式格式
2. 基于 E2B（开源）或 OpenSandbox 实现 sandbox 后端
3. 做 3-5 个垂直 Agent 示例（数据分析、Web 开发、DevOps）
4. 开源发布，吸引社区贡献 skills

12. 附录
12.1 术语表
术语	解释
microVM	轻量级虚拟机，有独立内核但极低资源开销（代表：Firecracker）
gVisor	Google 的用户态 Linux 内核，在用户空间拦截系统调用提供隔离
Kata Containers	将轻量 VM 封装为 OCI 兼容容器运行时的开源项目
WASM/WASI	WebAssembly 及其系统接口，提供平台无关的安全字节码执行
MCP	Model Context Protocol，Anthropic 提出的 AI 工具调用协议
Computer Use	Agent 通过模拟鼠标/键盘操作桌面应用的能力
Checkpoint/Restore	快照并恢复沙箱完整状态的能力
Ephemeral Sandbox	临时沙箱，会话结束后自动销毁
Persistent Sandbox	持久化沙箱，状态可跨会话保留
WarmPool	预热池，预先创建好的沙箱实例池，减少创建延迟
Defense-in-Depth	多层防御策略，组合多种隔离技术
OCI	Open Container Initiative，容器镜像和运行时标准
CRD	Custom Resource Definition，Kubernetes 自定义资源
BYOC	Bring Your Own Cloud，在客户自有云环境部署
12.2 参考链接
隔离技术
● Firecracker: https://github.com/firecracker-microvm/firecracker
● gVisor: https://github.com/google/gvisor
● Kata Containers: https://github.com/kata-containers/kata-containers
● WASI 标准: https://wasi.dev
沙箱平台
● E2B: https://e2b.dev / https://github.com/e2b-dev/E2B
● Daytona: https://www.daytona.io
● Sprites (Fly.io): https://sprites.dev
● Modal: https://modal.com
● Vercel Sandbox: https://vercel.com/docs/vercel-sandbox
● Deno Sandbox: https://deno.com/sandbox
● OpenSandbox: https://github.com/alibaba/OpenSandbox
● K8s Agent Sandbox: https://github.com/kubernetes-sigs/agent-sandbox
● Northflank: https://northflank.com/product/sandboxes
专项沙箱
● MCP Jail: https://mcpjail.com
● e2b-mcp: https://github.com/cased/e2b-mcp
● Browserbase: https://www.browserbase.com
● Steel: https://docs.steel.dev
● Firecrawl Browser: https://www.firecrawl.dev/browser
● Anthropic srt: https://github.com/anthropic-experimental/sandbox-runtime
● Matchlock: https://github.com/jingkaihe/matchlock
Agent 市场
● OnlyVercel: https://onlyvercel.com
● AgentDeploy: https://agentdeploy.io
● AgentSphere: https://www.agentsphere.run
分析与对比
● AI Agent Sandboxes Compared (Ry Walker): https://rywalker.com/research/ai-agent-sandboxes
● A Thousand Ways to Sandbox an Agent: https://michaellivs.com/blog/sandbox-comparison-2026/
● NVIDIA WASM Sandboxing Blog: https://developer.nvidia.com/blog/sandboxing-agentic-ai-workflows-with-webassembly/

报告完成时间：2026 年 3 月 16 日
数据截至：2026 年 3 月中旬