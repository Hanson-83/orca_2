"""Protocol 到 Orca WorkflowTemplate 的映射登记。"""

from pydantic import BaseModel, Field


class ProtocolMapping(BaseModel):
    """控制面协议名 → Orca 工作流模板名。

    层级对照（Phase 1 只使用到模板名这一层）：
    ProtocolMapping.name → WorkflowTemplate.name / @orca.workflow(name=...)
    任务提交 → Submission → Execution
    多样本 → labware groups；单板路径 → Labware Thread；步骤段 → Method；
    设备步 → Action → Operation(s) → Driver。
    """

    name: str
    workflow_template_name: str
    description: str = ""
    notes: str = Field(
        default=(
            "Phase1 只记录映射并由 MockRuntimeBackend 模拟时间线。"
            "真实提交走 daemon POST /executions，Phase2 才接线。"
        )
    )
