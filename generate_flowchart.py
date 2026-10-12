# -*- coding: utf-8 -*-
"""
四电梯调度算法流程图生成脚本（基于 elevator_scheduler.py 的实际逻辑）
输出：
  elevator_flow_main.png  —— 四电梯总体调度流程图
  elevator_flow_scan.png  —— 单部电梯 SCAN 单步运行子流程图
"""

from graphviz import Digraph

FONT = "Noto Sans CJK SC"

# ---------- 通用样式 ----------
C_START = "#aed6f1"   # 起止节点
C_PROC = "#ffffff"    # 处理节点
C_DEC = "#fdebd0"     # 判断节点
C_KEY = "#d6eaf8"     # 关键汇合节点
C_CLUSTER = "#f4f6f8" # 子图背景
C_GREEN = "#d5f5e3"   # 并行执行层


def base_style(g: Digraph):
    g.attr(rankdir="TB", bgcolor="white", nodesep="0.40", ranksep="0.52",
           fontname=FONT, dpi="200")
    g.attr("node", fontname=FONT, fontsize="12", style="filled",
           color="#2c3e50", fillcolor=C_PROC, penwidth="1.4")
    g.attr("edge", fontname=FONT, fontsize="10", color="#34495e",
            penwidth="1.2", arrowsize="0.8")


def start_node(g, name, label):
    g.node(name, label, shape="box", style="rounded,filled",
           fillcolor=C_START, penwidth="1.8")


def proc_node(g, name, label, fillcolor=C_PROC):
    g.node(name, label, shape="box", fillcolor=fillcolor)


def dec_node(g, name, label):
    g.node(name, label, shape="diamond", fillcolor=C_DEC, penwidth="1.5")


# =====================================================================
# 图 1：四电梯总体调度流程图
# =====================================================================
def build_main():
    g = Digraph("main", format="png")
    base_style(g)

    start_node(g, "start", "开始")
    proc_node(g, "init",
              "系统初始化\n楼栋总层数 N = 20，电梯数量 K = 4\n"
              "全部电梯停靠 1F，运行方向 = IDLE")
    dec_node(g, "d_new", "当前时间步\n是否有新的乘梯请求？")
    proc_node(g, "enqueue",
              "请求登记入队\n记录源楼层 source、目的楼层 dest、时间戳 t\n"
              "加入待分配队列 pending_requests")
    dec_node(g, "d_unassigned", "队列中是否存在\n未分配电梯的请求？")

    # ---- 调度代价评估 cluster ----
    with g.subgraph(name="cluster_cost") as c:
        c.attr(label="电梯选择层：对每部候选电梯 E_i（i = 0 … 3）评估综合调度代价",
               style="filled,rounded", fillcolor=C_CLUSTER,
               color="#7f8c8d", fontname=FONT, fontsize="12", penwidth="1.4")
        proc_node(c, "c0", "读取电梯 E_i 当前状态\n（所在楼层 / 运行方向 / 载客数 / 目标集合）", C_KEY)
        proc_node(c, "c1", "距离代价\nC_dist = |当前楼层 − 呼叫楼层|")
        proc_node(c, "c2", "方向惩罚 C_dir\n方向相反 +5\n正在远离呼叫层 +8")
        proc_node(c, "c3", "负载代价\nC_load = 载客数 × 2")
        proc_node(c, "c4", "拥堵与满载代价\nC_busy = 目标数 × 1.5\n满载额外 +100")
        proc_node(c, "csum",
                  "综合调度代价\nCost_i = C_dist + C_dir + C_load + C_busy", C_KEY)
        c.attr("node", shape="box")
        c.edge("c0", "c1")
        c.edge("c0", "c2")
        c.edge("c0", "c3")
        c.edge("c0", "c4")
        c.edge("c1", "csum")
        c.edge("c2", "csum")
        c.edge("c3", "csum")
        c.edge("c4", "csum")

    proc_node(g, "choose", "选定最优电梯\nE* = arg min  Cost_i（i = 0 … 3）", C_KEY)
    proc_node(g, "assign",
              "目标登记\n将接梯层 source 与目的层 dest\n"
              "按方向写入 E* 的上行 / 下行目标集合")

    # ---- 并行执行层 cluster ----
    with g.subgraph(name="cluster_run") as c:
        c.attr(label="并行执行层：四部电梯在同一时间步各自独立推进",
               style="filled,rounded", fillcolor=C_GREEN,
               color="#27ae60", fontname=FONT, fontsize="12", penwidth="1.4")
        for i in range(4):
            proc_node(c, f"e{i}",
                      f"电梯 E{i}\n执行 SCAN 单步运行\n（详见子流程图）", C_GREEN)
        c.body.append("{rank=same;e0;e1;e2;e3}")

    proc_node(g, "stop",
              "停站事件处理（仅在电梯开门停靠时）\n"
              "· 同层候乘乘客上车：载客数 +1，记录接梯时刻\n"
              "· 抵达目的层乘客下车：载客数 −1，服务计数 +1")
    proc_node(g, "cleanup", "已完成请求移出待处理队列\npending_requests")
    proc_node(g, "tinc", "仿真时间推进\nt ← t + 1")
    dec_node(g, "d_end", "达到仿真终止步数\n且请求队列已清空？")
    proc_node(g, "stats",
              "性能指标统计\n平均等待时间 / 平均乘梯时间 / 平均总耗时\n"
              "最大等待时间 / 各梯负载均衡率", C_KEY)
    start_node(g, "end", "结束")

    # ---- 主流程边 ----
    g.edge("start", "init")
    g.edge("init", "d_new")
    g.edge("d_new", "enqueue", label="是")
    g.edge("d_new", "d_unassigned", label="否")
    g.edge("enqueue", "d_unassigned")
    g.edge("d_unassigned", "c0", label="是")
    g.edge("d_unassigned", "e0", label="否（全部请求已分配）")
    g.edge("d_unassigned", "e1")
    g.edge("d_unassigned", "e2")
    g.edge("d_unassigned", "e3")
    g.edge("csum", "choose")
    g.edge("choose", "assign")
    g.edge("assign", "d_unassigned", label="继续分配下一请求",
           constraint="false", style="dashed", color="#8e44ad")
    for i in range(4):
        g.edge(f"e{i}", "stop")
    g.edge("stop", "cleanup")
    g.edge("cleanup", "tinc")
    g.edge("tinc", "d_end")
    g.edge("d_end", "d_new", label="否：进入下一时间步",
           constraint="false", style="dashed", color="#8e44ad")
    g.edge("d_end", "stats", label="是")
    g.edge("stats", "end")

    g.render("/workspace/elevator_flow_main", cleanup=True)
    print("generated: /workspace/elevator_flow_main.png")


# =====================================================================
# 图 2：单部电梯 SCAN 单步运行子流程图（对应 Elevator.step()）
# =====================================================================
def build_scan():
    g = Digraph("scan", format="png")
    base_style(g)
    g.attr(ranksep="0.45")

    start_node(g, "s_start", "单步运行开始\nElevator.step()")
    dec_node(g, "d_targets", "目标集合是否为空？\nup_targets ∪ down_targets = ∅")
    proc_node(g, "idle", "运行方向 ← IDLE", C_KEY)

    dec_node(g, "d_dir", "当前运行方向？")

    # 上行分支
    dec_node(g, "d_up", "上方是否存在同向目标？\n∃ f ∈ up_targets，f ≥ 当前层")
    proc_node(g, "n_up", "下一目标 next ←\nmin（上方同向目标）")
    dec_node(g, "d_dn2", "是否存在下行目标？")
    proc_node(g, "n_d1", "下一目标 next ←\nmax（下行目标）")

    # 下行分支
    dec_node(g, "d_down", "下方是否存在同向目标？\n∃ f ∈ down_targets，f ≤ 当前层")
    proc_node(g, "n_d2", "下一目标 next ←\nmax（下方同向目标）")
    dec_node(g, "d_up2", "是否存在上行目标？")
    proc_node(g, "n_u1", "下一目标 next ←\nmin（上行目标）")

    # 空闲分支
    proc_node(g, "n_idle", "下一目标 next ←\n距离最近的目标楼层\nmin |f − 当前层|")

    dec_node(g, "d_cmp", "next 与\n当前楼层比较？")
    proc_node(g, "set_up", "运行方向 ← UP")
    proc_node(g, "set_dn", "运行方向 ← DOWN")
    proc_node(g, "move",
              "移动一个楼层（当前层 ±1）\n运行楼层计数 travel_count += 1", C_KEY)

    dec_node(g, "door_check",
             "当前楼层是否属于\n当前运行方向的目标集合？")
    proc_node(g, "door",
              "开门停靠\n· 从目标集合移除当前楼层\n"
              "· 乘客上车 / 下车（载客数更新）", C_GREEN)
    dec_node(g, "d_remain", "是否仍有剩余目标？")
    proc_node(g, "set_idle", "运行方向 ← IDLE", C_KEY)
    start_node(g, "ret", "返回\n（开门楼层号 或 None）")

    # ---- 边 ----
    g.edge("s_start", "d_targets")
    g.edge("d_targets", "idle", label="是")
    g.edge("d_targets", "d_dir", label="否")
    g.edge("idle", "ret")

    g.edge("d_dir", "d_up", label="UP")
    g.edge("d_dir", "d_down", label="DOWN")
    g.edge("d_dir", "n_idle", label="IDLE")

    g.edge("d_up", "n_up", label="是")
    g.edge("d_up", "d_dn2", label="否")
    g.edge("d_dn2", "n_d1", label="是")
    g.edge("d_dn2", "idle", label="否")

    g.edge("d_down", "n_d2", label="是")
    g.edge("d_down", "d_up2", label="否")
    g.edge("d_up2", "n_u1", label="是")
    g.edge("d_up2", "idle", label="否")

    for n in ("n_up", "n_d1", "n_d2", "n_u1", "n_idle"):
        g.edge(n, "d_cmp")

    g.edge("d_cmp", "set_up", label="next > 当前层")
    g.edge("d_cmp", "set_dn", label="next < 当前层")
    g.edge("d_cmp", "door_check", label="next = 当前层（原地开门）")
    g.edge("set_up", "move")
    g.edge("set_dn", "move")
    g.edge("move", "door_check")

    g.edge("door_check", "door", label="是：到达目标层")
    g.edge("door_check", "d_remain", label="否：继续运行")
    g.edge("door", "d_remain")
    g.edge("d_remain", "set_idle", label="是：目标全部完成")
    g.edge("d_remain", "ret", label="否")
    g.edge("set_idle", "ret")

    # 三个方向分支水平对齐
    g.body.append("{rank=same;d_up;d_down;n_idle}")

    g.render("/workspace/elevator_flow_scan", cleanup=True)
    print("generated: /workspace/elevator_flow_scan.png")


if __name__ == "__main__":
    build_main()
    build_scan()
