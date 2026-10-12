"""
四电梯调度算法
==============
采用 SCAN（扫描）策略 + 最近优先调度：
- 每部电梯独立运行 SCAN 算法（同方向优先服务，到头再反转）
- 新的外部呼叫分配给"代价最小"的电梯（综合考虑距离、方向、负载）
- 支持模拟运行与可视化
"""

import random
from enum import Enum
from typing import List, Optional, Set


class Direction(Enum):
    UP = 1
    DOWN = -1
    IDLE = 0


class Elevator:
    """单部电梯状态"""

    def __init__(self, eid: int, total_floors: int):
        self.id = eid
        self.total_floors = total_floors
        self.current_floor = 1
        self.direction = Direction.IDLE
        self.passengers = 0           # 当前载客数
        self.capacity = 10            # 最大载客量
        self.up_targets: Set[int] = set()    # 上行目标楼层
        self.down_targets: Set[int] = set()  # 下行目标楼层
        self.travel_count = 0         # 运行楼层数（统计用）
        self.served_count = 0         # 服务乘客数（统计用）

    @property
    def targets(self) -> Set[int]:
        return self.up_targets | self.down_targets

    @property
    def is_full(self) -> bool:
        return self.passengers >= self.capacity

    def add_target(self, floor: int, direction: Optional[Direction] = None):
        """添加目标楼层"""
        if direction == Direction.UP or (direction is None and floor > self.current_floor):
            self.up_targets.add(floor)
        elif direction == Direction.DOWN or (direction is None and floor < self.current_floor):
            self.down_targets.add(floor)
        else:
            # 同层或方向空闲时，加入上行集合
            self.up_targets.add(floor)

    def _next_target(self) -> Optional[int]:
        """根据当前方向选择下一个目标楼层"""
        if self.direction == Direction.UP:
            # 上行时优先服务上方目标
            above = {f for f in self.up_targets if f >= self.current_floor}
            if above:
                return min(above)
            # 上方无目标，看看下方是否有下行目标
            if self.down_targets:
                return max(self.down_targets)
            return None

        elif self.direction == Direction.DOWN:
            below = {f for f in self.down_targets if f <= self.current_floor}
            if below:
                return max(below)
            if self.up_targets:
                return min(self.up_targets)
            return None

        else:  # IDLE
            if not self.targets:
                return None
            # 空闲时选择最近的目标
            all_targets = self.targets
            return min(all_targets, key=lambda f: abs(f - self.current_floor))

    def step(self) -> Optional[int]:
        """
        推进一步（一个时间单位）。
        返回当前到达的楼层，若电梯在某楼层开门则返回该楼层号，否则返回 None。
        """
        # 如果没有目标，保持空闲
        if not self.targets:
            self.direction = Direction.IDLE
            return None

        # 确定方向
        next_target = self._next_target()
        if next_target is None:
            self.direction = Direction.IDLE
            return None

        if next_target > self.current_floor:
            self.direction = Direction.UP
        elif next_target < self.current_floor:
            self.direction = Direction.DOWN

        # 移动一层
        if self.direction == Direction.UP:
            self.current_floor += 1
        elif self.direction == Direction.DOWN:
            self.current_floor -= 1
        self.travel_count += 1

        # 到达目标楼层则开门
        opened = False
        if self.current_floor in self.up_targets and self.direction in (Direction.UP, Direction.IDLE):
            self.up_targets.discard(self.current_floor)
            opened = True
        if self.current_floor in self.down_targets and self.direction in (Direction.DOWN, Direction.IDLE):
            self.down_targets.discard(self.current_floor)
            opened = True

        # 如果所有目标都完成了，变为空闲
        if not self.targets:
            self.direction = Direction.IDLE

        return self.current_floor if opened else None


class Request:
    """乘客请求"""

    def __init__(self, source: int, dest: int, time: int):
        self.source = source
        self.dest = dest
        self.time = time              # 请求产生的时间
        self.assigned: Optional[int] = None  # 分配的电梯 ID
        self.picked_up = False
        self.completed = False
        self.pickup_time: Optional[int] = None
        self.complete_time: Optional[int] = None

    @property
    def direction(self) -> Direction:
        return Direction.UP if self.dest > self.source else Direction.DOWN


class ElevatorScheduler:
    """四电梯调度器"""

    def __init__(self, total_floors: int = 20, num_elevators: int = 4):
        self.total_floors = total_floors
        self.elevators = [Elevator(i, total_floors) for i in range(num_elevators)]
        self.pending_requests: List[Request] = []
        self.completed_requests: List[Request] = []
        self.time = 0

    def _dispatch_cost(self, elevator: Elevator, request: Request) -> float:
        """
        计算将请求分配给某电梯的代价。
        代价越低越优先。综合考虑：
        1. 距离代价：电梯到请求楼层的距离
        2. 方向代价：如果电梯方向与请求方向相反，增加惩罚
        3. 负载代价：电梯越满代价越高
        4. 已有目标数代价：目标越多代价越高
        """
        distance = abs(elevator.current_floor - request.source)

        # 方向惩罚
        direction_penalty = 0
        if elevator.direction != Direction.IDLE:
            if elevator.direction != request.direction:
                direction_penalty = 5
            # 电梯正在远离请求楼层
            if (elevator.direction == Direction.UP and request.source < elevator.current_floor) or \
               (elevator.direction == Direction.DOWN and request.source > elevator.current_floor):
                direction_penalty += 8

        # 负载惩罚
        load_penalty = elevator.passengers * 2

        # 目标数惩罚（避免所有请求集中到一部电梯）
        target_penalty = len(elevator.targets) * 1.5

        # 满载惩罚
        full_penalty = 100 if elevator.is_full else 0

        return distance + direction_penalty + load_penalty + target_penalty + full_penalty

    def _assign_request(self, request: Request):
        """将请求分配给最优电梯"""
        best_elevator = None
        best_cost = float('inf')

        for elevator in self.elevators:
            cost = self._dispatch_cost(elevator, request)
            if cost < best_cost:
                best_cost = cost
                best_elevator = elevator

        if best_elevator is not None:
            request.assigned = best_elevator.id
            best_elevator.add_target(request.source, request.direction)
            # 同时将目的楼层也加入目标（电梯会在接客后添加，这里简化处理）
            best_elevator.add_target(request.dest)

    def add_request(self, source: int, dest: int):
        """添加乘客请求"""
        request = Request(source, dest, self.time)
        self.pending_requests.append(request)

    def step(self):
        """推进一步模拟"""
        # 分配所有未分配的请求
        for req in self.pending_requests:
            if req.assigned is None:
                self._assign_request(req)

        # 每部电梯执行一步
        for elevator in self.elevators:
            opened_floor = elevator.step()
            if opened_floor is not None:
                # 检查是否有乘客在此楼层上车
                for req in self.pending_requests:
                    if req.assigned == elevator.id and not req.picked_up and req.source == opened_floor:
                        req.picked_up = True
                        req.pickup_time = self.time
                        elevator.passengers += 1

                    # 检查是否有乘客在此楼层下车
                    if req.assigned == elevator.id and req.picked_up and not req.completed and req.dest == opened_floor:
                        req.completed = True
                        req.complete_time = self.time
                        elevator.passengers -= 1
                        elevator.served_count += 1
                        self.completed_requests.append(req)

        # 移除已完成的请求
        self.pending_requests = [r for r in self.pending_requests if not r.completed]
        self.time += 1

    def run(self, steps: int):
        """运行指定步数"""
        for _ in range(steps):
            self.step()

    def stats(self) -> dict:
        """统计信息"""
        if not self.completed_requests:
            return {"completed": 0}

        wait_times = [r.pickup_time - r.time for r in self.completed_requests if r.pickup_time is not None]
        travel_times = [r.complete_time - r.pickup_time for r in self.completed_requests if r.complete_time and r.pickup_time]
        total_times = [r.complete_time - r.time for r in self.completed_requests if r.complete_time is not None]

        return {
            "completed": len(self.completed_requests),
            "pending": len(self.pending_requests),
            "avg_wait_time": sum(wait_times) / len(wait_times) if wait_times else 0,
            "avg_travel_time": sum(travel_times) / len(travel_times) if travel_times else 0,
            "avg_total_time": sum(total_times) / len(total_times) if total_times else 0,
            "max_wait_time": max(wait_times) if wait_times else 0,
            "elevator_travel": [e.travel_count for e in self.elevators],
            "elevator_served": [e.served_count for e in self.elevators],
        }

    def display(self):
        """简单的文本可视化"""
        print(f"\n===== 时间步: {self.time} =====")
        for floor in range(self.total_floors, 0, -1):
            line = f"{floor:2d}F |"
            for elevator in self.elevators:
                if elevator.current_floor == floor:
                    arrow = {"UP": "↑", "DOWN": "↓", "IDLE": "·"}[elevator.direction.name]
                    line += f" [{arrow}{elevator.passengers}] "
                else:
                    line += "  .   "
            line += " |"
            # 显示该楼层的等待请求
            waiting = [r for r in self.pending_requests if r.source == floor and not r.picked_up]
            if waiting:
                dirs = "".join("↑" if r.direction == Direction.UP else "↓" for r in waiting)
                line += f"  等待:{dirs}"
            print(line)
        print("     " + "------" * len(self.elevators))
        print("     " + "".join(f" E{i}  " for i in range(len(self.elevators))))


def simulate():
    """运行模拟"""
    print("=" * 60)
    print("   四电梯调度算法模拟")
    print("   策略: SCAN + 最近优先调度")
    print("=" * 60)

    scheduler = ElevatorScheduler(total_floors=20, num_elevators=4)

    # 随机生成请求
    random.seed(42)
    request_schedule = {}
    num_requests = 60

    for _ in range(num_requests):
        t = random.randint(0, 80)
        source = random.randint(1, 20)
        dest = random.randint(1, 20)
        while dest == source:
            dest = random.randint(1, 20)
        if t not in request_schedule:
            request_schedule[t] = []
        request_schedule[t].append((source, dest))

    # 运行模拟
    total_steps = 150
    for step in range(total_steps):
        # 添加该时间步的请求
        if step in request_schedule:
            for src, dst in request_schedule[step]:
                scheduler.add_request(src, dst)

        scheduler.step()

        # 每 20 步显示一次
        if step % 20 == 0 or step == total_steps - 1:
            scheduler.display()

    # 继续运行直到所有请求完成
    extra = 0
    while scheduler.pending_requests and extra < 200:
        scheduler.step()
        extra += 1

    # 打印统计
    print("\n" + "=" * 60)
    print("   模拟统计")
    print("=" * 60)
    stats = scheduler.stats()
    print(f"  完成请求数:   {stats['completed']}")
    print(f"  剩余请求数:   {stats['pending']}")
    print(f"  平均等待时间: {stats['avg_wait_time']:.1f} 步")
    print(f"  平均乘梯时间: {stats['avg_travel_time']:.1f} 步")
    print(f"  平均总时间:   {stats['avg_total_time']:.1f} 步")
    print(f"  最大等待时间: {stats['max_wait_time']:.1f} 步")
    print(f"  各电梯运行层数: {stats['elevator_travel']}")
    print(f"  各电梯服务人数: {stats['elevator_served']}")

    # 负载均衡分析
    served = stats['elevator_served']
    if max(served) > 0:
        balance = min(served) / max(served) * 100
        print(f"  负载均衡率:   {balance:.0f}%")


if __name__ == "__main__":
    simulate()
