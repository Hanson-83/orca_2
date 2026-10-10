import "./styles.css";
import {
  api,
  eventSource,
  type AdapterHealth,
  type ClusterView,
  type ExperimentTask,
  type Health,
  type ProtocolMapping,
} from "./api";

const STATUS_LABEL: Record<string, string> = {
  pending: "待提交",
  queued: "已排队",
  running: "运行中",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
  idle: "空闲",
  busy: "忙碌",
  fault: "故障",
  offline: "离线",
  requested: "已请求",
  in_transit: "转运中",
  arrived: "已到达",
};

const app = document.querySelector("#app");
if (!app) {
  throw new Error("缺少 #app");
}

const notice = el("p", { class: "notice", id: "notice" });
const runtimePill = el("span", { class: "pill", id: "runtime-pill" }, ["执行面 …"]);
const authPill = el("span", { class: "pill" }, ["无认证 · 仅本机"]);
const streamPill = el("span", { class: "pill", id: "stream-pill" }, ["实时通道连接中"]);
const taskBody = el("tbody", { id: "task-body" });
const workcellBoard = el("div", { class: "cards", id: "workcell-board" });
const linkLine = el("p", { class: "muted", id: "link-line" }, ["链路加载中"]);
const transferBody = el("tbody", { id: "transfer-body" });
const adapterBoard = el("div", { class: "adapters", id: "adapter-board" });
const protocolSelect = el("select", { id: "protocol-ref", name: "protocol_ref" }) as HTMLSelectElement;
const workcellSelect = el("select", { id: "workcell-id", name: "workcell_id" }) as HTMLSelectElement;
const fromSelect = el("select", { id: "from-cell" }) as HTMLSelectElement;
const toSelect = el("select", { id: "to-cell" }) as HTMLSelectElement;
const nameInput = el("input", { id: "task-name", name: "name", required: "true", maxlength: "200" }) as HTMLInputElement;
const labwareInput = el("input", { id: "labware-id", value: "plate-demo" }) as HTMLInputElement;
const submitButton = el("button", { class: "primary", id: "submit-task", type: "submit" }, [
  "提交任务",
]) as HTMLButtonElement;

nameInput.placeholder = "例如：下午读板";

const form = el("form", { id: "task-form" }, [
  el("label", {}, ["任务名称", nameInput]),
  el("label", {}, ["协议", protocolSelect]),
  el("label", {}, ["工作单元", workcellSelect]),
  submitButton,
]);

const transferForm = el("form", { id: "transfer-form" }, [
  el("div", { class: "row" }, [
    el("label", {}, ["耗材", labwareInput]),
    el("label", {}, ["从", fromSelect]),
    el("label", {}, ["到", toSelect]),
    el("button", { type: "submit" }, ["请求转运"]),
  ]),
]);

app.append(
  el("div", { class: "shell" }, [
    el("header", { class: "top" }, [
      el("div", {}, [
        el("h1", {}, ["Orca MVC 控制面"]),
        el("p", {}, ["Phase 1 · 任务与工作单元。执行时间线是模拟的，尚未连接 Orca daemon。"]),
      ]),
      el("div", { class: "pills" }, [runtimePill, authPill, streamPill]),
    ]),
    notice,
    el("div", { class: "layout" }, [
      el("section", { class: "panel" }, [
        el("h2", {}, ["实验任务"]),
        el("div", { class: "table-wrap" }, [
          el("table", {}, [
            el("thead", {}, [
              el("tr", {}, [
                el("th", {}, ["名称"]),
                el("th", {}, ["协议"]),
                el("th", {}, ["工作单元"]),
                el("th", {}, ["状态"]),
                el("th", {}, ["执行引用"]),
              ]),
            ]),
            taskBody,
          ]),
        ]),
      ]),
      el("aside", { class: "stack" }, [
        el("section", { class: "panel" }, [el("h2", {}, ["提交任务"]), form]),
        el("section", { class: "panel" }, [el("h2", {}, ["适配器"]), adapterBoard]),
      ]),
    ]),
    el("section", { class: "stack" }, [
      el("div", { class: "panel" }, [
        el("h2", {}, ["工作单元"]),
        linkLine,
        workcellBoard,
      ]),
      el("div", { class: "panel" }, [
        el("h2", {}, ["跨单元转运"]),
        transferForm,
        el("div", { class: "table-wrap" }, [
          el("table", {}, [
            el("thead", {}, [
              el("tr", {}, [
                el("th", {}, ["耗材"]),
                el("th", {}, ["路径"]),
                el("th", {}, ["状态"]),
              ]),
            ]),
            transferBody,
          ]),
        ]),
      ]),
    ]),
  ]),
);

form.addEventListener("submit", (event) => {
  event.preventDefault();
  void submitTask();
});

transferForm.addEventListener("submit", (event) => {
  event.preventDefault();
  void requestTransfer();
});

let refreshing = false;

async function refresh(): Promise<void> {
  if (refreshing) return;
  refreshing = true;
  try {
    const [health, tasks, protocols, cluster, adapters] = await Promise.all([
      api<Health>("/api/v1/health"),
      api<ExperimentTask[]>("/api/v1/tasks"),
      api<ProtocolMapping[]>("/api/v1/protocols"),
      api<ClusterView>("/api/v1/cluster"),
      api<Record<string, AdapterHealth>>("/api/v1/adapters"),
    ]);
    runtimePill.textContent = `执行面 ${health.runtime} · ${health.version}`;
    renderTasks(tasks);
    fillSelect(
      protocolSelect,
      protocols.map((item) => ({
        value: item.name,
        label: item.description ? `${item.name} · ${item.description}` : item.name,
      })),
    );
    const cells = cluster.workcells.map((cell) => ({
      value: cell.id,
      label: `${cell.name}（${labelOf(cell.status)}）`,
    }));
    fillSelect(workcellSelect, cells);
    fillSelect(fromSelect, cells);
    fillSelect(toSelect, cells);
    renderCluster(cluster);
    renderAdapters(adapters);
    if (notice.textContent?.startsWith("无法连接")) {
      notice.textContent = "";
    }
  } catch (error) {
    notice.textContent = error instanceof Error ? `无法连接控制面：${error.message}` : "无法连接控制面";
  } finally {
    refreshing = false;
  }
}

function renderTasks(tasks: ExperimentTask[]): void {
  if (tasks.length === 0) {
    taskBody.replaceChildren(el("tr", {}, [el("td", { colspan: "5" }, ["还没有任务"])]));
    return;
  }
  taskBody.replaceChildren(
    ...tasks.map((task) =>
      el("tr", {}, [
        el("td", {}, [task.name]),
        el("td", { class: "mono" }, [task.protocol_ref]),
        el("td", { class: "mono" }, [task.workcell_id]),
        el("td", {}, [
          el("span", { class: `chip ${task.status}` }, [labelOf(task.status)]),
          task.error ? el("div", { class: "muted" }, [task.error]) : "",
        ]),
        el("td", { class: "mono" }, [task.execution_ref ?? "—"]),
      ]),
    ),
  );
}

function renderCluster(cluster: ClusterView): void {
  const linkText = cluster.links
    .map((link) => `${link.from_cell} → ${link.to_cell}（${link.link_type}${link.link_id ? ` / ${link.link_id}` : ""}）`)
    .join("，");
  linkLine.textContent = linkText ? `集群 ${cluster.id} · ${linkText}` : `集群 ${cluster.id} · 没有链路`;
  workcellBoard.replaceChildren(
    ...cluster.workcells.map((cell) =>
      el("article", { class: "card" }, [
        el("strong", {}, [cell.name]),
        el("div", {}, [el("span", { class: `chip ${cell.status}` }, [labelOf(cell.status)])]),
        el("p", { class: "muted" }, [
          `设备 ${cell.devices.join("、") || "无"} · 搬运 ${cell.transporters.join("、") || "无"}`,
        ]),
      ]),
    ),
  );
  if (cluster.transfers.length === 0) {
    transferBody.replaceChildren(el("tr", {}, [el("td", { colspan: "3" }, ["还没有转运"])]));
    return;
  }
  transferBody.replaceChildren(
    ...cluster.transfers.map((transfer) =>
      el("tr", {}, [
        el("td", { class: "mono" }, [transfer.labware_id]),
        el("td", { class: "mono" }, [`${transfer.from_cell} → ${transfer.to_cell}`]),
        el("td", {}, [el("span", { class: `chip ${transfer.state}` }, [labelOf(transfer.state)])]),
      ]),
    ),
  );
}

function renderAdapters(adapters: Record<string, AdapterHealth>): void {
  adapterBoard.replaceChildren(
    ...Object.values(adapters).map((adapter) => {
      const button = el("button", { type: "button" }, [adapter.name === "sila2" ? "模拟 SiLA2 调用" : "模拟 ROS2 调用"]);
      button.addEventListener("click", () => {
        void callAdapter(adapter.name);
      });
      const last = adapter.recent_calls.at(-1);
      return el("article", { class: "card" }, [
        el("strong", {}, [adapter.name.toUpperCase()]),
        el("div", {}, [
          el("span", { class: `chip ${adapter.status === "online" ? "completed" : "offline"}` }, [
            adapter.status === "online" ? "在线" : "离线",
          ]),
          ` ${adapter.mode} · 调用 ${adapter.call_count}`,
        ]),
        el("p", { class: "muted mono" }, [last ? JSON.stringify(last) : "还没有调用"]),
        button,
      ]);
    }),
  );
}

async function submitTask(): Promise<void> {
  submitButton.disabled = true;
  notice.textContent = "";
  try {
    const created = await api<ExperimentTask>("/api/v1/tasks", {
      method: "POST",
      body: JSON.stringify({
        name: nameInput.value.trim(),
        protocol_ref: protocolSelect.value,
        workcell_id: workcellSelect.value,
        run_mode: "MOCK",
      }),
    });
    await api<ExperimentTask>(`/api/v1/tasks/${created.id}/submit`, { method: "POST" });
    nameInput.value = "";
    await refresh();
  } catch (error) {
    notice.textContent = error instanceof Error ? error.message : "提交失败";
  } finally {
    submitButton.disabled = false;
  }
}

async function requestTransfer(): Promise<void> {
  notice.textContent = "";
  try {
    await api("/api/v1/cluster/transfers", {
      method: "POST",
      body: JSON.stringify({
        labware_id: labwareInput.value.trim(),
        from_cell: fromSelect.value,
        to_cell: toSelect.value,
      }),
    });
    await refresh();
  } catch (error) {
    notice.textContent = error instanceof Error ? error.message : "转运请求失败";
  }
}

async function callAdapter(name: string): Promise<void> {
  notice.textContent = "";
  try {
    if (name === "sila2") {
      await api("/api/v1/adapters/sila2/call", {
        method: "POST",
        body: JSON.stringify({ feature: "ShakerControl", command: "Shake", params: { rpm: 200 } }),
      });
    } else {
      await api("/api/v1/adapters/ros2/call", {
        method: "POST",
        body: JSON.stringify({
          kind: "service",
          service: "/workcell/arm/move",
          payload: { target: "home" },
        }),
      });
    }
    await refresh();
  } catch (error) {
    notice.textContent = error instanceof Error ? error.message : "适配器调用失败";
  }
}

function fillSelect(select: HTMLSelectElement, options: { value: string; label: string }[]): void {
  const current = select.value;
  select.replaceChildren(
    ...options.map((option) => el("option", { value: option.value }, [option.label])),
  );
  if (options.some((option) => option.value === current)) {
    select.value = current;
  }
}

function labelOf(value: string): string {
  return STATUS_LABEL[value] ?? value;
}

function connectStream(): void {
  const source = eventSource();
  const bump = () => {
    void refresh();
  };
  source.addEventListener("hello", () => {
    streamPill.textContent = "实时通道已连接";
  });
  for (const name of ["task.created", "task.updated", "cluster.loaded", "transfer.updated", "adapter.called"]) {
    source.addEventListener(name, bump);
  }
  source.onerror = () => {
    streamPill.textContent = "实时通道重连中";
  };
}

function el(tag: string, attrs: Record<string, string> = {}, children: (Node | string)[] = []): HTMLElement {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else node.setAttribute(key, value);
  }
  for (const child of children) {
    if (child === "") continue;
    node.append(child instanceof Node ? child : document.createTextNode(child));
  }
  return node;
}

void refresh();
window.setInterval(() => {
  void refresh();
}, 2000);
connectStream();
