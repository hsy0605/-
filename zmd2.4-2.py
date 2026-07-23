import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import json
import math
import uuid

# ======================= 游戏数据 =======================
EQUIPMENT_DATA = {
    "二型电驱矿机": {"power": 10, "size": (3, 3), "category": "采集"},
    "水泵": {"power": 10, "size": (3, 3), "category": "采集"},
    "源矿开采机": {"power": 0, "size": (3, 3), "category": "采集"},
    "研磨机": {"power": 20, "size": (3, 3), "category": "加工"},
    "粉碎机": {"power": 20, "size": (3, 3), "category": "加工"},
    "精炼炉": {"power": 20, "size": (4, 4), "category": "加工"},
    "反应池": {"power": 50, "size": (5, 5), "category": "化工"},
    "灌注机": {"power": 25, "size": (4, 4), "category": "化工"},
    "天有洪炉": {"power": 50, "size": (5, 5), "category": "化工"},
    "塑形机": {"power": 20, "size": (4, 4), "category": "制造"},
    "封装机": {"power": 20, "size": (6, 4), "category": "制造"},
    "装备原件机": {"power": 30, "size": (5, 5), "category": "制造"},
    "供电桩": {"power": 0, "size": (2, 2), "category": "电力"},
    "协议核心": {"power": 0, "size": (3, 3), "category": "电力"},
    "仓库取货口": {"power": 0, "size": (2, 2), "category": "物流"},
    "协议储存箱": {"power": 0, "size": (3, 3), "category": "物流"},
    "仓库存取线源桩": {"power": 0, "size": (4, 4), "category": "物流"},
    "仓库存取线基段": {"power": 0, "size": (8, 4), "category": "物流"},
    "息壤中继器": {"power": 0, "size": (2, 2), "category": "物流"},
    "滑索架": {"power": 5, "size": (3, 3), "category": "物流"},
}

RECIPES = {
    "铁制零件": {"inputs": {"源矿": 2}, "device": "研磨机", "time": 5},
    "稳定碳块": {"inputs": {"碳块": 2}, "device": "精炼炉", "time": 4},
    "息壤": {"inputs": {"稳定碳块": 2, "清水": 1}, "device": "天有洪炉", "time": 6},
    "液化息壤": {"inputs": {"息壤": 1, "清水": 1}, "device": "反应池", "time": 4},
    "锦草粉末": {"inputs": {"锦草": 1}, "device": "研磨机", "time": 3},
    "芽针粉末": {"inputs": {"芽针": 1}, "device": "研磨机", "time": 3},
    "锦草溶液": {"inputs": {"锦草粉末": 1, "清水": 1}, "device": "反应池", "time": 5},
    "芽针溶液": {"inputs": {"芽针粉末": 1, "清水": 1}, "device": "反应池", "time": 5},
    "蓝铁瓶": {"inputs": {"蓝铁矿": 2}, "device": "塑形机", "time": 5},
    "电池": {"inputs": {"紫晶矿": 3, "稳定碳块": 1}, "device": "封装机", "time": 10},
    "装备": {"inputs": {"铁制零件": 5, "蓝铁瓶": 1}, "device": "装备原件机", "time": 15},
    "炸药": {"inputs": {"紫晶零件": 2, "酮化灌木": 1}, "device": "封装机", "time": 8},
    "药品": {"inputs": {"锦草溶液": 1, "芽针溶液": 1}, "device": "灌注机", "time": 6},
}

DEVICE_TO_PRODUCTS = {}
for prod, recipe in RECIPES.items():
    DEVICE_TO_PRODUCTS.setdefault(recipe["device"], []).append(prod)

ALL_ITEMS = set(RECIPES.keys())
for recipe in RECIPES.values():
    ALL_ITEMS.update(recipe["inputs"].keys())
ALL_ITEMS = sorted(ALL_ITEMS)

POWER_RADIUS = {
    "协议核心": 8,
    "供电桩": 4,
}


class FactoryPlanner:
    def __init__(self, root):
        self.root = root
        root.title("明日方舟：终末地 工业规划器 (完整拖拽版)")
        root.geometry("1200x750")

        self.devices = {}            # uuid -> 设备数据
        self.connections = {}        # (from_uuid, to_uuid) -> {line_id, label_id}
        self.power_sources = []      # 供电设备uuid列表
        self._highlighted = []

        self.grid_pixel = 20
        self.mode = "select"
        self.connect_first = None

        # 拖拽状态
        self.drag_device_name = None
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.drag_active = False
        self.drag_potential = False
        self.drag_ghost_id = None
        self.drag_threshold = 5

        # 撤销/重做
        self.undo_stack = []
        self.redo_stack = []
        self._skip_history = False

        # 倒计时
        self.timer_running = False
        self.remaining_time = 0
        self.timer_id = None

        self.setup_ui()
        self.bind_shortcuts()

    def setup_ui(self):
        # ----- 左侧面板 -----
        left_frame = tk.Frame(self.root, width=280, bg="#f0f0f0")
        left_frame.pack(side=tk.LEFT, fill=tk.Y)
        left_frame.pack_propagate(False)

        tk.Label(left_frame, text="设备列表（拖拽到画布）", bg="#f0f0f0", font=("Arial", 12, "bold")).pack(pady=5)
        self.device_listbox = tk.Listbox(left_frame, height=12, font=("Arial", 10))
        self.device_listbox.pack(fill=tk.X, padx=5, pady=5)
        for name in sorted(EQUIPMENT_DATA.keys()):
            self.device_listbox.insert(tk.END, name)
        self.device_listbox.bind("<ButtonPress-1>", self.on_list_press)

        # 操作模式
        tk.Label(left_frame, text="操作模式", bg="#f0f0f0", font=("Arial", 12, "bold")).pack(pady=(5,0))
        btn_frame = tk.Frame(left_frame, bg="#f0f0f0")
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        tk.Button(btn_frame, text="选择", command=lambda: self.set_mode("select"), bg="#ccffcc").pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="连线", command=lambda: self.set_mode("connect"), bg="#ffffcc").pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="删除", command=lambda: self.set_mode("delete"), bg="#ffcccc").pack(side=tk.LEFT, padx=2)

        # 效率模拟
        tk.Label(left_frame, text="生产模拟", bg="#f0f0f0", font=("Arial", 12, "bold")).pack(pady=(5,0))
        sim_frame = tk.Frame(left_frame, bg="#f0f0f0")
        sim_frame.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(sim_frame, text="目标物品:", bg="#f0f0f0").pack(side=tk.LEFT)
        self.target_var = tk.StringVar()
        self.target_combo = ttk.Combobox(sim_frame, textvariable=self.target_var, values=ALL_ITEMS, width=12)
        self.target_combo.pack(side=tk.LEFT, padx=5)
        tk.Button(sim_frame, text="模拟", command=self.simulate_production).pack(side=tk.LEFT, padx=5)

        # 倒计时
        tk.Label(left_frame, text="电力负载倒计时", bg="#f0f0f0", font=("Arial", 12, "bold")).pack(pady=(5,0))
        timer_frame = tk.Frame(left_frame, bg="#f0f0f0")
        timer_frame.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(timer_frame, text="秒数:", bg="#f0f0f0").pack(side=tk.LEFT)
        self.timer_entry = tk.Entry(timer_frame, width=6)
        self.timer_entry.insert(0, "30")
        self.timer_entry.pack(side=tk.LEFT, padx=5)
        self.timer_start_btn = tk.Button(timer_frame, text="启动倒计时", command=self.start_timer)
        self.timer_start_btn.pack(side=tk.LEFT, padx=2)
        self.timer_reset_btn = tk.Button(timer_frame, text="重置供电", command=self.reset_power)
        self.timer_reset_btn.pack(side=tk.LEFT, padx=2)
        self.timer_label = tk.Label(left_frame, text="剩余时间: --", bg="#f0f0f0", font=("Arial", 10))
        self.timer_label.pack(pady=5)

        # 蓝图
        file_frame = tk.Frame(left_frame, bg="#f0f0f0")
        file_frame.pack(fill=tk.X, padx=5, pady=5)
        tk.Button(file_frame, text="保存蓝图", command=self.save_blueprint).pack(side=tk.LEFT, padx=2)
        tk.Button(file_frame, text="加载蓝图", command=self.load_blueprint).pack(side=tk.LEFT, padx=2)
        tk.Button(file_frame, text="清空画布", command=self.clear_canvas).pack(side=tk.LEFT, padx=2)

        self.status_var = tk.StringVar()
        self.status_var.set("就绪 | 从左侧列表拖拽设备到画布放置 | Ctrl+Z/Y 撤销重做")
        status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # ----- 右侧主区域 -----
        right_frame = tk.Frame(self.root)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(right_frame, bg="white")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.draw_grid()

        # 画布事件（左键单击用于查看设备/连线删除，右键用于设置产品）
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.tag_bind("connection_line", "<Button-3>", self.delete_connection_by_click)
        self.root.bind("<Escape>", self.cancel_drag)

        # 信息面板
        info_frame = tk.Frame(right_frame, width=250, bg="#e8e8e8")
        info_frame.pack(side=tk.RIGHT, fill=tk.Y)
        info_frame.pack_propagate(False)

        tk.Label(info_frame, text="设备详情", bg="#e8e8e8", font=("Arial", 12, "bold")).pack(pady=5)
        self.info_text = tk.Text(info_frame, height=12, width=30, font=("Arial", 10))
        self.info_text.pack(padx=5, pady=5, fill=tk.X)
        self.info_text.config(state=tk.DISABLED)

        tk.Label(info_frame, text="统计", bg="#e8e8e8", font=("Arial", 12, "bold")).pack(pady=(10,0))
        self.stats_label = tk.Label(info_frame, text="设备: 0\n总耗电: 0W\n占地面积: 0 格\n供电正常: 0",
                                    bg="#e8e8e8", font=("Arial", 10), justify=tk.LEFT)
        self.stats_label.pack(padx=5, pady=5, anchor=tk.W)

    def bind_shortcuts(self):
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-y>", lambda e: self.redo())

    def draw_grid(self):
        self.canvas.delete("grid")
        for x in range(0, 5000, self.grid_pixel):
            self.canvas.create_line(x, 0, x, 5000, fill="#e0e0e0", tags="grid")
        for y in range(0, 5000, self.grid_pixel):
            self.canvas.create_line(0, y, 5000, y, fill="#e0e0e0", tags="grid")
        self.canvas.tag_lower("grid")

    # ==================== 拖拽处理 ====================
    def on_list_press(self, event):
        if self.mode != "select":
            return
        idx = self.device_listbox.nearest(event.y)
        if idx >= 0:
            self.device_listbox.selection_clear(0, tk.END)
            self.device_listbox.selection_set(idx)
            self.drag_device_name = self.device_listbox.get(idx)
            self.drag_start_x = event.x_root
            self.drag_start_y = event.y_root
            self.drag_potential = True
            self.drag_active = False
            # 绑定全局移动和释放
            self.root.bind("<B1-Motion>", self.on_global_motion, add="+")
            self.root.bind("<ButtonRelease-1>", self.on_global_release, add="+")

    def on_global_motion(self, event):
        if not self.drag_device_name:
            return
        if not self.drag_active:
            dx = event.x_root - self.drag_start_x
            dy = event.y_root - self.drag_start_y
            if abs(dx) > self.drag_threshold or abs(dy) > self.drag_threshold:
                self.drag_active = True
                self.root.config(cursor="crosshair")
                self.status_var.set(f"拖拽 {self.drag_device_name} 到画布...")
        if self.drag_active:
            canvas_x = event.x_root - self.canvas.winfo_rootx()
            canvas_y = event.y_root - self.canvas.winfo_rooty()
            self.update_ghost(canvas_x, canvas_y)

    def update_ghost(self, canvas_x, canvas_y):
        dev_info = EQUIPMENT_DATA[self.drag_device_name]
        w, h = dev_info["size"]
        px_w = w * self.grid_pixel
        px_h = h * self.grid_pixel
        snap_x = round(canvas_x / self.grid_pixel) * self.grid_pixel
        snap_y = round(canvas_y / self.grid_pixel) * self.grid_pixel
        x0 = snap_x - px_w // 2
        y0 = snap_y - px_h // 2

        if self.drag_ghost_id is None:
            self.drag_ghost_id = self.canvas.create_rectangle(
                x0, y0, x0+px_w, y0+px_h,
                outline="gray", width=2, dash=(4,4), fill="", stipple="gray50",
                tags="drag_ghost")
        else:
            self.canvas.coords(self.drag_ghost_id, x0, y0, x0+px_w, y0+px_h)

    def on_global_release(self, event):
        self.root.unbind("<B1-Motion>")
        self.root.unbind("<ButtonRelease-1>")
        if self.drag_active:
            widget = self.root.winfo_containing(event.x_root, event.y_root)
            if widget == self.canvas:
                canvas_x = event.x_root - self.canvas.winfo_rootx()
                canvas_y = event.y_root - self.canvas.winfo_rooty()
                dev_info = EQUIPMENT_DATA[self.drag_device_name]
                w, h = dev_info["size"]
                px_w = w * self.grid_pixel
                px_h = h * self.grid_pixel
                snap_x = round(canvas_x / self.grid_pixel) * self.grid_pixel
                snap_y = round(canvas_y / self.grid_pixel) * self.grid_pixel
                x0 = snap_x - px_w // 2
                y0 = snap_y - px_h // 2
                overlapping = self.canvas.find_overlapping(x0, y0, x0+px_w, y0+px_h)
                if any(item in self._get_rect_id_map() for item in overlapping):
                    self.status_var.set("该位置已被占用，请选择其他位置")
                else:
                    self.place_device_at(x0, y0, self.drag_device_name)
                    self.status_var.set(f"已放置 {self.drag_device_name}")
            else:
                self.status_var.set("请在画布上释放以放置设备")
        self.cancel_drag()

    def cancel_drag(self, event=None):
        if self.drag_ghost_id:
            self.canvas.delete(self.drag_ghost_id)
            self.drag_ghost_id = None
        self.drag_active = False
        self.drag_potential = False
        self.drag_device_name = None
        self.root.config(cursor="")
        self.root.unbind("<B1-Motion>")
        self.root.unbind("<ButtonRelease-1>")

    # ==================== 画布普通点击 ====================
    def on_canvas_click(self, event):
        if self.drag_active:
            return
        if self.mode == "delete":
            item = self.canvas.find_closest(event.x, event.y)
            if item:
                tags = self.canvas.gettags(item[0])
                if "connection_line" in tags:
                    self.delete_connection_by_item(item[0])
                    return

    def on_device_click(self, dev_uuid):
        if self.mode == "select":
            self.show_device_info(dev_uuid)
        elif self.mode == "connect":
            self.handle_connect(dev_uuid)
        elif self.mode == "delete":
            self.delete_device(dev_uuid)

    def set_mode(self, mode):
        self.mode = mode
        self.cancel_drag()
        if mode == "select":
            self.status_var.set("选择模式：点击设备查看详情，从列表拖拽设备放置，右键设置产品")
        elif mode == "connect":
            self.connect_first = None
            self.status_var.set("连线模式：依次点击两个设备创建传送带")
        elif mode == "delete":
            self.status_var.set("删除模式：点击设备或连线删除")
        self.clear_highlights()

    def clear_highlights(self):
        for uid in self._highlighted:
            if uid in self.devices:
                self.canvas.itemconfig(self.devices[uid]["rect_id"], outline="black", width=2)
        self._highlighted.clear()

    # ==================== 放置设备 ====================
    def place_device_at(self, x0, y0, device_name):
        dev_info = EQUIPMENT_DATA[device_name]
        w, h = dev_info["size"]
        px_w = w * self.grid_pixel
        px_h = h * self.grid_pixel

        dev_uuid = str(uuid.uuid4())
        rect_id = self.canvas.create_rectangle(x0, y0, x0+px_w, y0+px_h,
                                               fill="lightblue", outline="black", width=2,
                                               tags="device_rect")
        text_id = self.canvas.create_text(x0+px_w//2, y0+px_h//2,
                                          text=device_name, font=("Arial", 8),
                                          anchor="center", tags="device_text")
        self.devices[dev_uuid] = {
            "uuid": dev_uuid,
            "name": device_name,
            "x": x0, "y": y0,
            "width": px_w, "height": px_h,
            "rect_id": rect_id,
            "text_id": text_id,
            "powered": True,
            "product": None,
            "power_zone": None
        }

        if device_name in POWER_RADIUS:
            self.power_sources.append(dev_uuid)
            self.draw_power_zone(dev_uuid)

        self.canvas.tag_bind(rect_id, "<Button-1>", lambda e, uid=dev_uuid: self.on_device_click(uid))
        self.canvas.tag_bind(text_id, "<Button-1>", lambda e, uid=dev_uuid: self.on_device_click(uid))
        self.update_power_status()
        self.update_stats()
        self.push_history({
            "type": "place",
            "uuid": dev_uuid,
            "snapshot": self._snapshot_device(dev_uuid),
            "connections": []
        })

    # ==================== 制造链路展示 ====================
    def get_chain_text(self, item, depth=0, max_depth=2):
        indent = "  " * depth
        if item not in RECIPES:
            return f"{indent}{item} (基础材料/采集)"
        recipe = RECIPES[item]
        inputs = recipe["inputs"]
        dev = recipe["device"]
        parts = []
        for mat, qty in inputs.items():
            if mat in RECIPES:
                sub_dev = RECIPES[mat]["device"]
                parts.append(f"{mat} x{qty} (由{sub_dev}生产)")
            else:
                parts.append(f"{mat} x{qty} (基础材料)")
        line = f"{indent}{item} <- {dev} : " + " + ".join(parts) + f" (耗时{recipe['time']}s)"
        if depth < max_depth:
            sub_lines = []
            for mat in inputs.keys():
                if mat in RECIPES:
                    sub_lines.append(self.get_chain_text(mat, depth+1, max_depth))
            if sub_lines:
                line += "\n" + "\n".join(sub_lines)
        return line

    def show_device_info(self, dev_uuid):
        if dev_uuid not in self.devices:
            return
        obj = self.devices[dev_uuid]
        name = obj["name"]
        dev_info = EQUIPMENT_DATA[name]
        power = dev_info["power"]
        size = dev_info["size"]
        products = DEVICE_TO_PRODUCTS.get(name, [])
        prod_str = ", ".join(products) if products else "（无）"
        powered = "是" if obj["powered"] else "否"
        info = f"设备: {name}\n耗电: {power}W\n尺寸: {size[0]}x{size[1]} 格\n供电: {powered}\n可生产: {prod_str}"

        if products:
            info += "\n\n制造链路:"
            for prod in products:
                chain = self.get_chain_text(prod, depth=0, max_depth=2)
                info += "\n" + chain
        else:
            info += "\n\n（该设备不直接生产任何物品）"

        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(tk.END, info)
        self.info_text.config(state=tk.DISABLED)

        self.clear_highlights()
        self.canvas.itemconfig(obj["rect_id"], outline="red", width=3)
        self._highlighted.append(dev_uuid)

    # ==================== 连线系统 ====================
    def handle_connect(self, dev_uuid):
        if self.connect_first is None:
            self.connect_first = dev_uuid
            self.canvas.itemconfig(self.devices[dev_uuid]["rect_id"], outline="blue", width=3)
            self.status_var.set("请点击第二个设备")
        else:
            if dev_uuid == self.connect_first:
                self.canvas.itemconfig(self.devices[self.connect_first]["rect_id"], outline="black", width=2)
                self.connect_first = None
                self.status_var.set("连线取消")
                return
            self._draw_connection_line(self.connect_first, dev_uuid)
            self.canvas.itemconfig(self.devices[self.connect_first]["rect_id"], outline="black", width=2)
            self.connect_first = None
            self.status_var.set("连接创建成功")

    def _draw_connection_line(self, from_uuid, to_uuid):
        obj1 = self.devices[from_uuid]
        obj2 = self.devices[to_uuid]
        x1 = obj1["x"] + obj1["width"] // 2
        y1 = obj1["y"] + obj1["height"] // 2
        x2 = obj2["x"] + obj2["width"] // 2
        y2 = obj2["y"] + obj2["height"] // 2
        line_id = self.canvas.create_line(x1, y1, x2, y2, fill="orange", width=3,
                                          arrow=tk.LAST, tags="connection_line")
        product = obj1["product"]
        label_id = None
        if product:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            label_id = self.canvas.create_text(mx, my, text=product, font=("Arial", 7),
                                               fill="darkorange", tags="connection_label")
        self.connections[(from_uuid, to_uuid)] = {
            "line_id": line_id,
            "label_id": label_id
        }
        self.push_history({
            "type": "connect",
            "from_uuid": from_uuid,
            "to_uuid": to_uuid,
            "connection": {
                "from_uuid": from_uuid,
                "to_uuid": to_uuid,
                "line_id": line_id,
                "label_id": label_id
            }
        })

    # ==================== 删除 ====================
    def delete_device(self, dev_uuid):
        if dev_uuid not in self.devices:
            return
        snapshot = self._snapshot_device(dev_uuid)
        associated_conns = []
        for (from_uuid, to_uuid), data in list(self.connections.items()):
            if from_uuid == dev_uuid or to_uuid == dev_uuid:
                associated_conns.append({
                    "from_uuid": from_uuid,
                    "to_uuid": to_uuid,
                    "line_id": data["line_id"],
                    "label_id": data.get("label_id")
                })
        self.push_history({
            "type": "delete",
            "uuid": dev_uuid,
            "snapshot": snapshot,
            "connections": associated_conns
        })
        self._delete_device(dev_uuid, record=False)

    def _delete_device(self, dev_uuid, record=True):
        if dev_uuid not in self.devices:
            return
        to_del = []
        for (from_uuid, to_uuid), data in self.connections.items():
            if from_uuid == dev_uuid or to_uuid == dev_uuid:
                self.canvas.delete(data["line_id"])
                if data.get("label_id"):
                    self.canvas.delete(data["label_id"])
                to_del.append((from_uuid, to_uuid))
        for key in to_del:
            del self.connections[key]

        if dev_uuid in self.power_sources:
            self.power_sources.remove(dev_uuid)
        dev = self.devices[dev_uuid]
        if dev.get("power_zone"):
            self.canvas.delete(dev["power_zone"])
        self.canvas.delete(dev["rect_id"])
        self.canvas.delete(dev["text_id"])
        del self.devices[dev_uuid]
        self.redraw_power_zones()
        self.update_power_status()
        self.update_stats()

    def delete_connection_by_click(self, event):
        item = self.canvas.find_closest(event.x, event.y)
        if item:
            self.delete_connection_by_item(item[0])

    def delete_connection_by_item(self, item_id):
        for (from_uuid, to_uuid), data in list(self.connections.items()):
            if data["line_id"] == item_id:
                self._remove_connection(from_uuid, to_uuid, record=True)
                return

    def _remove_connection(self, from_uuid, to_uuid, record=True):
        if (from_uuid, to_uuid) not in self.connections:
            return
        data = self.connections.pop((from_uuid, to_uuid))
        self.canvas.delete(data["line_id"])
        if data.get("label_id"):
            self.canvas.delete(data["label_id"])
        if record:
            self.push_history({
                "type": "disconnect",
                "from_uuid": from_uuid,
                "to_uuid": to_uuid,
                "connection": {
                    "from_uuid": from_uuid,
                    "to_uuid": to_uuid,
                    "line_id": data["line_id"],
                    "label_id": data.get("label_id")
                }
            })

    # ==================== 供电系统 ====================
    def draw_power_zone(self, dev_uuid):
        dev = self.devices[dev_uuid]
        name = dev["name"]
        radius = POWER_RADIUS.get(name, 0)
        if radius == 0:
            return
        cx = dev["x"] + dev["width"] // 2
        cy = dev["y"] + dev["height"] // 2
        r_px = radius * self.grid_pixel
        zone = self.canvas.create_oval(cx-r_px, cy-r_px, cx+r_px, cy+r_px,
                                       outline="green", width=1, stipple="gray50",
                                       fill="", tags="power_zone")
        dev["power_zone"] = zone

    def update_power_zone(self, dev_uuid):
        if dev_uuid in self.devices and self.devices[dev_uuid].get("power_zone"):
            self.canvas.delete(self.devices[dev_uuid]["power_zone"])
            self.draw_power_zone(dev_uuid)

    def redraw_power_zones(self):
        for uid in self.power_sources:
            if uid in self.devices:
                if self.devices[uid].get("power_zone"):
                    self.canvas.delete(self.devices[uid]["power_zone"])
                self.draw_power_zone(uid)

    def update_power_status(self):
        if self.timer_running and self.remaining_time == 0:
            return
        for uid, dev in self.devices.items():
            name = dev["name"]
            if name in POWER_RADIUS:
                dev["powered"] = True
                continue
            powered = False
            cx = dev["x"] + dev["width"] // 2
            cy = dev["y"] + dev["height"] // 2
            for src_uid in self.power_sources:
                src = self.devices.get(src_uid)
                if not src:
                    continue
                radius = POWER_RADIUS.get(src["name"], 0)
                if radius == 0:
                    continue
                scx = src["x"] + src["width"] // 2
                scy = src["y"] + src["height"] // 2
                if math.hypot(cx - scx, cy - scy) <= radius * self.grid_pixel:
                    powered = True
                    break
            dev["powered"] = powered
            color = "lightblue" if powered else "lightgray"
            self.canvas.itemconfig(dev["rect_id"], fill=color)
        self.update_stats()

    # ==================== 倒计时 ====================
    def start_timer(self):
        if self.timer_running:
            return
        try:
            seconds = int(self.timer_entry.get())
            if seconds <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("错误", "请输入有效的正整数秒数")
            return
        self.remaining_time = seconds
        self.timer_running = True
        self.timer_start_btn.config(state=tk.DISABLED)
        self.timer_label.config(text=f"剩余时间: {self.remaining_time} 秒")
        self.update_timer()

    def update_timer(self):
        if self.remaining_time > 0:
            self.remaining_time -= 1
            self.timer_label.config(text=f"剩余时间: {self.remaining_time} 秒")
            self.timer_id = self.root.after(1000, self.update_timer)
        else:
            self.power_outage()

    def power_outage(self):
        self.timer_running = False
        self.timer_start_btn.config(state=tk.NORMAL)
        self.timer_label.config(text="⚠️ 电力中断！")
        self.status_var.set("电力负载过大，所有设备已停止！")
        for uid, dev in self.devices.items():
            dev["powered"] = False
            self.canvas.itemconfig(dev["rect_id"], fill="gray")
            if uid in self.power_sources and dev.get("power_zone"):
                self.canvas.delete(dev["power_zone"])
                dev["power_zone"] = None
        self.update_stats()

    def reset_power(self):
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
            self.timer_id = None
        self.timer_running = False
        self.timer_start_btn.config(state=tk.NORMAL)
        self.timer_label.config(text="供电已恢复")
        self.status_var.set("供电已重置")
        self.redraw_power_zones()
        self.update_power_status()
        self.update_stats()

    # ==================== 效率模拟 ====================
    def simulate_production(self):
        target = self.target_var.get()
        if not target:
            messagebox.showinfo("提示", "请选择目标物品")
            return

        active_devices = {uid: dev for uid, dev in self.devices.items()
                          if dev["product"] and dev["powered"]}
        if not active_devices:
            messagebox.showinfo("提示", "没有已供电且设置了产品的设备")
            return

        device_index = {uid: i for i, uid in enumerate(active_devices)}
        N = len(active_devices)
        max_rates = [0.0] * N
        input_demands = [{} for _ in range(N)]
        products = [None] * N

        for uid, dev in active_devices.items():
            idx = device_index[uid]
            product = dev["product"]
            products[idx] = product
            if product in RECIPES:
                recipe = RECIPES[product]
                max_rates[idx] = 1.0 / recipe["time"]
                input_demands[idx] = dict(recipe["inputs"])
            else:
                max_rates[idx] = 1.0 / 5.0
                input_demands[idx] = {}

        supplies = [{} for _ in range(N)]
        for (from_uuid, to_uuid), _ in self.connections.items():
            if from_uuid in device_index and to_uuid in device_index:
                u = device_index[from_uuid]
                v = device_index[to_uuid]
                p = products[u]
                if p in input_demands[v]:
                    if p not in supplies[v]:
                        supplies[v][p] = []
                    supplies[v][p].append(u)

        MAX_ITER = 500
        EPS = 1e-6
        DAMPING = 0.5
        r = list(max_rates)
        for _ in range(MAX_ITER):
            r_new = [0.0] * N
            max_diff = 0.0
            for i in range(N):
                if not input_demands[i]:
                    r_new[i] = max_rates[i]
                else:
                    bottleneck = float('inf')
                    for item, amount in input_demands[i].items():
                        total_supply = 0.0
                        if item in supplies[i]:
                            for u in supplies[i][item]:
                                total_supply += r[u]
                        supported = total_supply / amount if amount > 0 else float('inf')
                        if supported < bottleneck:
                            bottleneck = supported
                    if bottleneck == float('inf'):
                        bottleneck = 0.0
                    r_new[i] = min(max_rates[i], bottleneck)
                new_val = r[i] * (1 - DAMPING) + r_new[i] * DAMPING
                max_diff = max(max_diff, abs(new_val - r[i]))
                r[i] = new_val
            if max_diff < EPS:
                break

        report = f"生产模拟: {target}\n" + "="*35 + "\n"
        for uid, dev in active_devices.items():
            idx = device_index[uid]
            product = dev["product"]
            max_rate = max_rates[idx]
            actual_rate = r[idx]
            eff = (actual_rate / max_rate * 100) if max_rate > 0 else 0
            report += f"{dev['name']} ({product})\n"
            report += f"  最大速率: {max_rate:.3f}/s\n"
            report += f"  实际速率: {actual_rate:.3f}/s\n"
            report += f"  效率: {eff:.1f}%\n"
            if eff < 99.9 and max_rate > 0:
                if not input_demands[idx]:
                    report += "  (源头设备，受下游需求限制)\n"
                else:
                    for item, amount in input_demands[idx].items():
                        total_supply = 0.0
                        if item in supplies[idx]:
                            for u in supplies[idx][item]:
                                total_supply += r[u]
                        need = amount * max_rate
                        if total_supply < need * 0.99:
                            report += f"  瓶颈: {item} 供应不足 (需{need:.3f}, 实{total_supply:.3f})\n"
            report += "\n"

        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(tk.END, report)
        self.info_text.config(state=tk.DISABLED)
        self.status_var.set(f"效率模拟完成: {target}")

    # ==================== 右键菜单（设置产品） ====================
    def on_right_click(self, event):
        item = self.canvas.find_closest(event.x, event.y)
        if item:
            dev_uuid = self._find_device_by_rect(item[0])
            if dev_uuid:
                self.popup_product_selector(dev_uuid)

    def popup_product_selector(self, dev_uuid):
        win = tk.Toplevel(self.root)
        win.title("选择设备产品")
        win.geometry("300x400")
        win.grab_set()
        tk.Label(win, text="选择该设备生产的产品：", font=("Arial", 10)).pack(pady=5)
        frame = tk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox = tk.Listbox(frame, yscrollcommand=scrollbar.set, font=("Arial", 10))
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)
        for item in ALL_ITEMS:
            listbox.insert(tk.END, item)

        def on_confirm():
            sel = listbox.curselection()
            if not sel:
                messagebox.showwarning("未选择", "请选择一个产品", parent=win)
                return
            product = listbox.get(sel[0])
            self.devices[dev_uuid]["product"] = product
            self.update_device_label(dev_uuid)
            for (from_uuid, to_uuid), data in self.connections.items():
                if from_uuid == dev_uuid:
                    if data.get("label_id"):
                        self.canvas.itemconfigure(data["label_id"], text=product)
            win.destroy()
            self.status_var.set(f"设备 {self.devices[dev_uuid]['name']} 现在生产 {product}")

        def on_clear():
            self.devices[dev_uuid]["product"] = None
            self.update_device_label(dev_uuid)
            for (from_uuid, to_uuid), data in self.connections.items():
                if from_uuid == dev_uuid and data.get("label_id"):
                    self.canvas.itemconfigure(data["label_id"], text="")
            win.destroy()
            self.status_var.set("已清除产品设定")

        btn_frame = tk.Frame(win)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="确认", command=on_confirm, width=8).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="清除产品", command=on_clear, width=8).pack(side=tk.LEFT, padx=5)

    def update_device_label(self, dev_uuid):
        dev = self.devices[dev_uuid]
        text = dev["name"]
        if dev["product"]:
            text += f"\n({dev['product']})"
        self.canvas.itemconfig(dev["text_id"], text=text)

    # ==================== 撤销/重做 ====================
    def push_history(self, action):
        if self._skip_history:
            return
        self.undo_stack.append(action)
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            return
        self._skip_history = True
        action = self.undo_stack.pop()
        if action["type"] == "place":
            self._delete_device(action["uuid"], record=False)
        elif action["type"] == "delete":
            self._restore_device(action["snapshot"])
            for conn in action["connections"]:
                self._restore_connection(conn)
        elif action["type"] == "connect":
            self._remove_connection(action["from_uuid"], action["to_uuid"], record=False)
        elif action["type"] == "disconnect":
            self._restore_connection(action["connection"])
        self.redo_stack.append(action)
        self._skip_history = False
        self.update_stats()

    def redo(self):
        if not self.redo_stack:
            return
        self._skip_history = True
        action = self.redo_stack.pop()
        if action["type"] == "place":
            self._restore_device(action["snapshot"])
            for conn in action.get("connections", []):
                self._restore_connection(conn)
        elif action["type"] == "delete":
            self._delete_device(action["uuid"], record=False)
        elif action["type"] == "connect":
            self._restore_connection(action["connection"])
        elif action["type"] == "disconnect":
            self._remove_connection(action["from_uuid"], action["to_uuid"], record=False)
        self.undo_stack.append(action)
        self._skip_history = False
        self.update_stats()

    def _restore_device(self, snapshot):
        uid = snapshot["uuid"]
        rect_id = self.canvas.create_rectangle(
            snapshot["x"], snapshot["y"],
            snapshot["x"] + snapshot["width"], snapshot["y"] + snapshot["height"],
            fill="lightblue", outline="black", width=2, tags="device_rect")
        text_id = self.canvas.create_text(
            snapshot["x"] + snapshot["width"]//2, snapshot["y"] + snapshot["height"]//2,
            text=snapshot["name"], font=("Arial", 8), anchor="center", tags="device_text")
        self.devices[uid] = {
            "uuid": uid,
            "name": snapshot["name"],
            "x": snapshot["x"], "y": snapshot["y"],
            "width": snapshot["width"], "height": snapshot["height"],
            "rect_id": rect_id,
            "text_id": text_id,
            "powered": snapshot["powered"],
            "product": snapshot.get("product"),
            "power_zone": None
        }
        self.canvas.tag_bind(rect_id, "<Button-1>", lambda e, u=uid: self.on_device_click(u))
        self.canvas.tag_bind(text_id, "<Button-1>", lambda e, u=uid: self.on_device_click(u))
        if snapshot["name"] in POWER_RADIUS:
            self.power_sources.append(uid)
            self.draw_power_zone(uid)
        self.update_power_status()

    def _restore_connection(self, conn_data):
        self._draw_connection_line(conn_data["from_uuid"], conn_data["to_uuid"])

    def _snapshot_device(self, dev_uuid):
        dev = self.devices[dev_uuid]
        return {
            "uuid": dev_uuid,
            "name": dev["name"],
            "x": dev["x"], "y": dev["y"],
            "width": dev["width"], "height": dev["height"],
            "powered": dev["powered"],
            "product": dev["product"]
        }

    # ==================== 蓝图 ====================
    def save_blueprint(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".json",
                                                 filetypes=[("JSON files", "*.json")])
        if not file_path:
            return
        devices_data = []
        for uid, dev in self.devices.items():
            devices_data.append({
                "uuid": uid,
                "name": dev["name"],
                "x": dev["x"],
                "y": dev["y"],
                "width": dev["width"],
                "height": dev["height"],
                "product": dev["product"]
            })
        conns_data = []
        for (from_uuid, to_uuid), _ in self.connections.items():
            conns_data.append({"from_uuid": from_uuid, "to_uuid": to_uuid})
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({"devices": devices_data, "connections": conns_data}, f,
                      indent=2, ensure_ascii=False)
        self.status_var.set(f"蓝图已保存至 {file_path}")

    def load_blueprint(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            messagebox.showerror("错误", "加载失败")
            return
        self.clear_canvas(ask=False)
        for dev_data in data.get("devices", []):
            uid = dev_data["uuid"]
            name = dev_data["name"]
            x0, y0 = dev_data["x"], dev_data["y"]
            w, h = dev_data["width"], dev_data["height"]
            rect_id = self.canvas.create_rectangle(x0, y0, x0+w, y0+h,
                                                   fill="lightblue", outline="black", width=2,
                                                   tags="device_rect")
            text_id = self.canvas.create_text(x0+w//2, y0+h//2, text=name,
                                              font=("Arial", 8), anchor="center", tags="device_text")
            self.devices[uid] = {
                "uuid": uid,
                "name": name,
                "x": x0, "y": y0,
                "width": w, "height": h,
                "rect_id": rect_id,
                "text_id": text_id,
                "powered": True,
                "product": dev_data.get("product"),
                "power_zone": None
            }
            if name in POWER_RADIUS:
                self.power_sources.append(uid)
                self.draw_power_zone(uid)
            self.canvas.tag_bind(rect_id, "<Button-1>", lambda e, u=uid: self.on_device_click(u))
            self.canvas.tag_bind(text_id, "<Button-1>", lambda e, u=uid: self.on_device_click(u))
            self.update_device_label(uid)

        for conn in data.get("connections", []):
            from_uuid = conn["from_uuid"]
            to_uuid = conn["to_uuid"]
            if from_uuid in self.devices and to_uuid in self.devices:
                self._draw_connection_line(from_uuid, to_uuid)

        self.update_power_status()
        self.update_stats()
        self.status_var.set("蓝图加载完成")
        self.undo_stack.clear()
        self.redo_stack.clear()

    def clear_canvas(self, ask=True):
        if ask and not messagebox.askyesno("确认", "清空所有设备？"):
            return
        for uid in list(self.devices.keys()):
            self.canvas.delete(self.devices[uid]["rect_id"])
            self.canvas.delete(self.devices[uid]["text_id"])
            if self.devices[uid].get("power_zone"):
                self.canvas.delete(self.devices[uid]["power_zone"])
        for data in self.connections.values():
            self.canvas.delete(data["line_id"])
            if data.get("label_id"):
                self.canvas.delete(data["label_id"])
        self.devices.clear()
        self.connections.clear()
        self.power_sources.clear()
        self.clear_highlights()
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete(1.0, tk.END)
        self.info_text.config(state=tk.DISABLED)
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.update_stats()
        self.status_var.set("画布已清空")

    def update_stats(self):
        count = len(self.devices)
        total_power = 0
        total_area = 0
        powered_count = 0
        for dev in self.devices.values():
            name = dev["name"]
            if name in EQUIPMENT_DATA:
                total_power += EQUIPMENT_DATA[name]["power"]
                w, h = EQUIPMENT_DATA[name]["size"]
                total_area += w * h
            if dev["powered"]:
                powered_count += 1
        self.stats_label.config(
            text=f"设备: {count}\n总耗电: {total_power}W\n占地面积: {total_area} 格\n供电正常: {powered_count}")

    def _get_rect_id_map(self):
        return {dev["rect_id"]: uid for uid, dev in self.devices.items()}

    def _find_device_by_rect(self, rect_id):
        for uid, dev in self.devices.items():
            if dev["rect_id"] == rect_id:
                return uid
        return None

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    root = tk.Tk()
    app = FactoryPlanner(root)
    app.run()