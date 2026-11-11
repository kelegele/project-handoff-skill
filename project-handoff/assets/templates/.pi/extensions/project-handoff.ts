/**
 * project-handoff 的 pi 适配扩展：把 pi 生命周期事件转成 Claude 风格钩子协议，
 * 喂给共享 agent_hook.py；记录逻辑全在 python 侧，本文件只转发事件、回填输出。
 * 安装：复制到项目 .pi/extensions/project-handoff.ts，并把 HOOK_SCRIPT 替换为共享脚本绝对路径。
 */
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { execFile } from "node:child_process";

const HOOK_SCRIPT = "__HOOK_SCRIPT__";
const TIMEOUT_MS = 3000;
type HookEventName = "SessionStart" | "UserPromptSubmit" | "Stop" | "Interrupt" | "SessionEnd";

// 任何失败静默返回 null：记录失败不得阻塞任务（与 python 侧兜底哲学一致）
async function runHook(ctx: ExtensionContext, name: HookEventName): Promise<any | null> {
  return await new Promise((resolve) => {
    try {
      const child = execFile("python3", [HOOK_SCRIPT, "--agent", "Pi"],
        { timeout: TIMEOUT_MS }, (_err, stdout) => {
          if (!stdout) return resolve(null);
          try { resolve(JSON.parse(stdout.trim().split("\n").pop() ?? "")); }
          catch { resolve(null); }
        });
      child.stdin?.on("error", () => {});
      child.stdin?.end(JSON.stringify({
        hook_event_name: name,
        session_id: ctx.sessionManager.getSessionFile() ?? `ephemeral-${process.pid}`,
        cwd: ctx.cwd,
        pid: process.pid,
      }));
    } catch { resolve(null); }
  });
}

export default function (pi: ExtensionAPI) {
  pi.on("session_start", async (_event, ctx) => {
    const out = await runHook(ctx, "SessionStart");
    const context = out?.hookSpecificOutput?.additionalContext;
    if (typeof context === "string" && context) {
      // 排队入下一条用户消息的上下文，不触发回合；只在会话启动注入一次，避免逐条累积
      pi.sendMessage({ customType: "project-handoff", content: context, display: false },
        { deliverAs: "nextTurn" });
    }
  });

  pi.on("before_agent_start", async (event, ctx) => {
    if (event.messageType !== "user") return;
    await runHook(ctx, "UserPromptSubmit");
  });

  pi.on("agent_settled", async (event, ctx) => {
    // agent_end 后 pi 仍可能自动重试/续跑，settled 才是回合真终点
    const out = await runHook(ctx, event.aborted ? "Interrupt" : "Stop");
    const msg = out?.systemMessage;
    if (ctx.hasUI && typeof msg === "string" && msg) ctx.ui.notify(msg, "warning");
  });

  pi.on("session_shutdown", async (event, ctx) => {
    if (event.reason !== "quit") return; // new/resume/fork 是会话切换，不算结束
    await runHook(ctx, "SessionEnd");
  });
}
