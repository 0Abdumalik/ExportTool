
#by malik
#2025.2.21

# 导入必要的模块
import maya.cmds as cmds
import maya.mel as mel
import os
import json
from PySide2 import QtCore, QtGui, QtWidgets
import shiboken2

# 修改 JSON 文件路径为脚本所在目录下的 export_presets.json
JSON_FILE_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'export_presets.json')

# 获取Maya主窗口作为QWidget
def get_maya_window():
    from shiboken2 import wrapInstance
    import maya.OpenMayaUI as omui
    maya_main_window_ptr = omui.MQtUtil.mainWindow()
    maya_main_window = wrapInstance(int(maya_main_window_ptr), QtWidgets.QWidget)
    return maya_main_window

# 导出工具的主类
class ExportTool(QtWidgets.QDialog):
    def __init__(self, parent=get_maya_window()):
        super(ExportTool, self).__init__(parent)

        self.setWindowTitle("导出工具")
        self.setMinimumSize(800, 600)

        # 存储每个引用对象的UI元素
        self.ref_ui_elements = {}

        # 初始化JSON文件加载状态
        self.json_loaded = False

        # 加载预设
        self.load_presets()

        # 构建UI
        self.build_ui()

    def load_presets(self):
        json_file = JSON_FILE_PATH
        if not os.path.exists(json_file):
            # 自动生成默认预设文件
            default_presets = {
                "default_file": {
                    "预设1": {
                        "导出方式": {
                            "fbx": {
                                "导出的fbx名称": "default.fbx",
                                "导出的模型": ["model1", "model2"]
                            },
                            "abc": {
                                "导出的abc名称": "default.abc",
                                "导出的模型": ["model1", "model2"]
                            }
                        },
                        "导出是否烘培": False,
                        "不导出的模型": []
                    }
                }
            }
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(default_presets, f, ensure_ascii=False, indent=4)
            cmds.warning("未找到预设JSON文件，自动生成默认预设文件：{}".format(json_file))
            self.presets = default_presets
            self.json_loaded = True
        else:
            with open(json_file, 'r', encoding='utf-8') as f:
                self.presets = json.load(f)
                self.json_loaded = True

    def build_ui(self):
        # 保留最上方工具菜单（恢复预设编辑器菜单）
        menu_bar = QtWidgets.QMenuBar(self)
        tool_menu = menu_bar.addMenu("工具")
        preset_manager_action = QtWidgets.QAction("预设编辑器", self)
        preset_manager_action.triggered.connect(show_preset_manager)
        tool_menu.addAction(preset_manager_action)
        # 其它菜单项也可以添加……
        # 将menu_bar添加到界面顶部
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addWidget(menu_bar)
        self.jsonStatusLabel = QtWidgets.QLabel()
        main_layout.addWidget(self.jsonStatusLabel)
        self.update_json_status_panel()
        
        # 主体区域采用水平布局，分为【引用面板】，【导出台】，【日志】
        main_container = QtWidgets.QWidget()
        h_layout = QtWidgets.QHBoxLayout(main_container)
        
        # 左侧【引用面板】：展示所有引用对象，每个项含“导出”按钮
        self.referenceScrollArea = QtWidgets.QScrollArea()
        self.referenceScrollArea.setWidgetResizable(True)
        ref_container = QtWidgets.QWidget()
        self.referenceLayout = QtWidgets.QVBoxLayout(ref_container)
        # 遍历引用对象，调用 create_reference_ui（仅生成引用信息，不含预设管理部分）
        references = cmds.file(q=True, reference=True)
        if references:
            for ref in references:
                namespace = cmds.file(ref, q=True, namespace=True)
                filename = os.path.basename(ref)
                self.create_reference_ui(namespace, filename)
        else:
            cmds.warning("场景中未找到引用对象。")
        self.referenceScrollArea.setWidget(ref_container)
        h_layout.addWidget(self.referenceScrollArea)

        # 中间【导出台】：任务列表及总导出按钮
        export_panel = QtWidgets.QWidget()
        v_export_layout = QtWidgets.QVBoxLayout(export_panel)
        # 新增导出文件夹选择控件
        folder_layout = QtWidgets.QHBoxLayout()
        folder_layout.addWidget(QtWidgets.QLabel("导出文件夹:"))
        self.folder_line_edit = QtWidgets.QLineEdit()
        folder_layout.addWidget(self.folder_line_edit)
        choose_folder_btn = QtWidgets.QPushButton("选择文件夹")
        choose_folder_btn.clicked.connect(self.select_folder)
        folder_layout.addWidget(choose_folder_btn)
        v_export_layout.addLayout(folder_layout)
        v_export_layout.addWidget(QtWidgets.QLabel("导出台"))
        # 导出任务列表滚动区域
        self.exportScrollArea = QtWidgets.QScrollArea()
        self.exportScrollArea.setWidgetResizable(True)
        export_container = QtWidgets.QWidget()
        self.exportJobLayout = QtWidgets.QVBoxLayout(export_container)
        export_container.setLayout(self.exportJobLayout)
        self.exportScrollArea.setWidget(export_container)
        v_export_layout.addWidget(self.exportScrollArea)
        # 按钮区域：总导出按钮 与 删除所选任务按钮
        button_layout = QtWidgets.QHBoxLayout()
        total_export_btn = QtWidgets.QPushButton("总导出")
        total_export_btn.clicked.connect(self.export)
        del_task_btn = QtWidgets.QPushButton("删除所选任务")
        del_task_btn.clicked.connect(self.delete_selected_tasks)
        button_layout.addWidget(total_export_btn)
        button_layout.addWidget(del_task_btn)
        v_export_layout.addLayout(button_layout)
        # 在总进度条前增加提示
        progress_wrapper = QtWidgets.QHBoxLayout()
        progress_wrapper.addWidget(QtWidgets.QLabel("总进度:"))
        self.totalProgressBar = QtWidgets.QProgressBar()
        self.totalProgressBar.setMinimum(0)
        self.totalProgressBar.setMaximum(100)
        self.totalProgressBar.setFormat("%p%")
        progress_wrapper.addWidget(self.totalProgressBar)
        v_export_layout.addLayout(progress_wrapper)
        h_layout.addWidget(export_panel)

        # 右侧【日志】：显示日志和清空日志按钮
        log_panel = QtWidgets.QWidget()
        v_log_layout = QtWidgets.QVBoxLayout(log_panel)
        self.logTextEdit = QtWidgets.QTextEdit()
        self.logTextEdit.setReadOnly(True)
        v_log_layout.addWidget(QtWidgets.QLabel("日志"))
        v_log_layout.addWidget(self.logTextEdit)
        clear_log_btn = QtWidgets.QPushButton("清空日志")
        clear_log_btn.clicked.connect(self.logTextEdit.clear)
        v_log_layout.addWidget(clear_log_btn)
        h_layout.addWidget(log_panel)

        main_layout.addWidget(main_container)

    # 新增方法：将某个引用的导出任务添加至导出台
    def add_reference_export_task(self, namespace, filename, preset_combo, version_combo, format_combo):
        task_info = {
            "引用对象": namespace,
            "命名空间": namespace,
            "文件名": filename,
            "预设": preset_combo.currentText(),
            "格式": format_combo.currentText(),  # 例如："Binary"或"ASCII"
            "FBX版本": version_combo.currentText(),
            "目录": self.folder_line_edit.text() if hasattr(self, 'folder_line_edit') else "",
            "当前进度": 0,
            "JSON状态": ""
        }
        panel, prog_bar = self.add_export_job_panel(task_info)
        self.logTextEdit.append(f"添加导出任务：{namespace}")

    # 修改 create_reference_ui：每个引用项仅显示引用信息并添加一个【导出】按钮
    def create_reference_ui(self, namespace, filename):
        group_box = QtWidgets.QGroupBox(f"引用对象: {namespace}")
        layout = QtWidgets.QVBoxLayout(group_box)
        # 第一行：文件名与预设选择
        row1 = QtWidgets.QHBoxLayout()
        file_label = QtWidgets.QLabel(f"文件: {filename}")
        row1.addWidget(file_label)
        row1.addWidget(QtWidgets.QLabel("预设:"))
        preset_combo = QtWidgets.QComboBox()
        # 根据预设数据填充，如果无对应数据，则显示默认
        if filename in self.presets and self.presets[filename]:
            preset_combo.addItems(list(self.presets[filename].keys()))
        else:
            preset_combo.addItem("默认预设")
        row1.addWidget(preset_combo)
        layout.addLayout(row1)
        # 第二行：增加FBX版本与格式选择
        row2 = QtWidgets.QHBoxLayout()
        row2.addWidget(QtWidgets.QLabel("版本:"))
        version_combo = QtWidgets.QComboBox()
        # 可根据实际需求增减版本
        version_combo.addItems(["FBX2018", "FBX2016", "FBX2014"])
        row2.addWidget(version_combo)
        row2.addWidget(QtWidgets.QLabel("格式:"))
        format_combo = QtWidgets.QComboBox()
        format_combo.addItems(["Binary", "ASCII"])
        row2.addWidget(format_combo)
        layout.addLayout(row2)
        # 第三行：选择复选框和导出按钮
        row3 = QtWidgets.QHBoxLayout()
        chk = QtWidgets.QCheckBox("选择")
        chk.setChecked(True)
        row3.addWidget(chk)
        export_btn = QtWidgets.QPushButton("导出")
        # 将预设、版本和格式下拉框作为参数传入导出任务
        export_btn.clicked.connect(lambda: self.add_reference_export_task(namespace, filename, preset_combo, version_combo, format_combo))
        row3.addWidget(export_btn)
        layout.addLayout(row3)
        self.referenceLayout.addWidget(group_box)
        self.ref_ui_elements[namespace] = {'filename': filename, 'selected': chk, 'preset_combo': preset_combo,
                                           'version_combo': version_combo, 'format_combo': format_combo}

    # 新增方法：导出任务面板添加保持不变
    def add_export_job_panel(self, job_info):
        panel = QtWidgets.QGroupBox(f"导出任务：{job_info.get('引用对象','')}")
        # 使用表单布局创建详细信息区域
        form_layout = QtWidgets.QFormLayout(panel)
        # 新增：在顶部插入一个复选框，用于选择本任务
        select_chk = QtWidgets.QCheckBox("选中")
        form_layout.insertRow(0, select_chk)
        panel.select_checkbox = select_chk
        form_layout.addRow("命名空间：", QtWidgets.QLabel(job_info.get("命名空间", "")))
        form_layout.addRow("文件名：", QtWidgets.QLabel(job_info.get("文件名", "")))
        form_layout.addRow("预设：", QtWidgets.QLabel(job_info.get("预设", "")))
        form_layout.addRow("格式：", QtWidgets.QLabel(job_info.get("格式", "")))
        form_layout.addRow("FBX版本：", QtWidgets.QLabel(job_info.get("FBX版本", "")))
        form_layout.addRow("导出目录：", QtWidgets.QLabel(job_info.get("目录", "")))
        progress_bar = QtWidgets.QProgressBar()
        progress_bar.setMinimum(0)
        progress_bar.setMaximum(100)
        progress_bar.setValue(job_info.get("当前进度", 0))
        progress_bar.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        form_layout.addRow("任务进度：", progress_bar)
        self.exportJobLayout.addWidget(panel)
        return panel, progress_bar

    # update_json_status_panel 方法保持不变（或略作调整输出到 self.jsonStatusLabel）
    def update_json_status_panel(self, read_state=""):
        if os.path.exists(JSON_FILE_PATH):
            file_info = os.stat(JSON_FILE_PATH)
            saved_time = QtCore.QDateTime.fromSecsSinceEpoch(int(file_info.st_mtime)).toString("yyyy-MM-dd hh:mm:ss")
            status_text = (
                f"位置：{os.path.dirname(JSON_FILE_PATH)}  "
                f"文件名：{os.path.basename(JSON_FILE_PATH)}  "
                f"读取状态：{'有' if self.json_loaded else '无'}  "
                f"最后保存时间：{saved_time}"
            )
        else:
            status_text = "无 JSON 文件加载"
        self.jsonStatusLabel.setText(status_text)
        # 同时更新导出台面顶部的 JSON 状态（可复刻）
        # 可根据需要同步到其他控件

    # 修改 export 方法：遍历导出台中的任务顺序执行
    def export(self):
        self.logTextEdit.append("开始总导出任务...")
        count = self.exportJobLayout.count()
        if count == 0:
            self.logTextEdit.append("没有任务需要导出。")
            return
        progress_increment = 100 / count
        total_progress = 0
        for i in range(count):
            task_widget = self.exportJobLayout.itemAt(i).widget()
            self.logTextEdit.append(f"正在导出任务 {i+1}...")
            # 此处调用具体导出逻辑（可根据任务中的数据调用 process_export 等）
            # 模拟延时
            QtWidgets.QApplication.processEvents()
            total_progress += progress_increment
            self.totalProgressBar.setValue(int(total_progress))
        self.logTextEdit.append("所有任务导出完成。")
        self.totalProgressBar.setValue(100)

    # 新增方法：删除导出任务（在导出台中删除被选中的任务面板）
    def delete_selected_tasks(self):
        count = self.exportJobLayout.count()
        remove_list = []
        for i in range(count):
            widget = self.exportJobLayout.itemAt(i).widget()
            # 若任务面板具有select_checkbox且勾选，则加入删除列表
            if hasattr(widget, "select_checkbox") and widget.select_checkbox.isChecked():
                remove_list.append(widget)
        if not remove_list:
            self.logTextEdit.append("请选中要删除的任务！")
            return
        for w in remove_list:
            w.setParent(None)
        self.logTextEdit.append(f"删除了 {len(remove_list)} 个任务。")

    # 增加文件夹选择控件（如果需要在导出任务中传入目录）
    def select_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "选择导出文件夹")
        if folder:
            # 假设用一个行编辑框保存目录（如果不存在，则新建）
            if not hasattr(self, 'folder_line_edit'):
                self.folder_line_edit = QtWidgets.QLineEdit()
                self.folder_line_edit.setText(folder)
            else:
                self.folder_line_edit.setText(folder)

    # 新增：切换任务面板选中状态（模拟选中效果）
    def toggle_task_selection(self, widget):
        # 为简单起见，设置一个属性 isSelected
        if hasattr(widget, "isSelected") and widget.isSelected:
            widget.isSelected = False
            widget.setStyleSheet("")  # 清除高亮
        else:
            widget.isSelected = True
            widget.setStyleSheet("background-color: lightblue;")

    def process_export(self, namespace, preset, export_folder, fbx_format, fbx_version):
        # ...保持原有逻辑不变...
        self.progress_bar1.setValue(0)
        QtWidgets.QApplication.processEvents()
        steps = 1
        if preset.get('导出方式', {}).get('abc'):
            steps = 2
        progress_increment = 100 / steps
        current_progress = 0
        mel.eval('FBXResetExport();')
        mel.eval('FBXExportFileVersion -v "{}";'.format(fbx_version))
        mel.eval('FBXExportInAscii -v {};'.format('True' if fbx_format == 'ASCII' else 'False'))
        bake_animation = preset.get('导出是否烘培', False)
        start_frame = cmds.playbackOptions(q=True, min=True)
        end_frame = cmds.playbackOptions(q=True, max=True)
        models_to_export = preset.get('导出的模型', [])
        exclude_models = preset.get('不导出的模型', [])
        models_with_namespace = [namespace + ':' + m for m in models_to_export]
        exclude_with_namespace = [namespace + ':' + m for m in exclude_models]
        cmds.select(models_with_namespace, replace=True)
        if exclude_with_namespace:
            cmds.select(exclude_with_namespace, deselect=True)
        if bake_animation:
            meshes = cmds.ls(selection=True, type='transform')
            joints = set()
            for mesh in meshes:
                history = cmds.listHistory(mesh) or []
                skin_clusters = cmds.ls(history, type='skinCluster') or []
                for skin in skin_clusters:
                    influences = cmds.skinCluster(skin, q=True, influence=True) or []
                    joints.update(influences)
            joints = list(joints)
            if joints:
                cmds.bakeResults(joints, t=(start_frame, end_frame), simulation=True)
        fbx_export = preset.get('导出方式', {}).get('fbx', {})
        fbx_name = fbx_export.get('导出的fbx名称', 'exported.fbx')
        fbx_path = os.path.join(export_folder, fbx_name)
        cmds.file(fbx_path, force=True, options="v=0;", type="FBX export", exportSelected=True)
        current_progress += progress_increment
        self.progress_bar1.setValue(int(current_progress))
        QtWidgets.QApplication.processEvents()
        if preset.get('导出方式', {}).get('abc'):
            abc_export = preset['导出方式']['abc']
            abc_name = abc_export.get('导出的abc名称', 'exported.abc')
            abc_models = abc_export.get('导出的模型', [])
            abc_models_with_namespace = [namespace + ':' + m for m in abc_models]
            cmds.select(abc_models_with_namespace, replace=True)
            abc_path = os.path.join(export_folder, abc_name)
            cmds.AbcExport(j='-frameRange {} {} -uvWrite -worldSpace -writeVisibility -file "{}"'.format(start_frame, end_frame, abc_path))
            current_progress += progress_increment
            self.progress_bar1.setValue(int(current_progress))
            QtWidgets.QApplication.processEvents()
        self.progress_bar1.setValue(100)
        QtWidgets.QApplication.processEvents()
        cmds.select(clear=True)

# 预设编辑器代码开始
class PresetManager(QtWidgets.QDialog):
    def __init__(self, parent=get_maya_window()):
        super(PresetManager, self).__init__(parent)
        self.setWindowTitle("导出预设管理器")
        self.setMinimumSize(800, 600)
        self.presets = {}
        self.current_json_path = ""
        self.build_ui()
        self.reload_modules()

    def reload_modules(self):
        import sys
        module_name = __name__
        if (module_name in sys.modules):
            import importlib
            importlib.reload(sys.modules[module_name])

    def build_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        # 新增 JSON 文件选择区域
        json_select_layout = QtWidgets.QHBoxLayout()
        self.jsonSelectCombo = QtWidgets.QComboBox()  # 用于显示根目录下所有 json 文件
        refresh_json_btn = QtWidgets.QPushButton("刷新")
        refresh_json_btn.clicked.connect(self.update_json_list)
        json_select_layout.addWidget(QtWidgets.QLabel("JSON 文件选择："))
        json_select_layout.addWidget(self.jsonSelectCombo)
        json_select_layout.addWidget(refresh_json_btn)
        main_layout.addLayout(json_select_layout)
        # 新增 JSON 状态显示区域
        self.jsonStatusLabel = QtWidgets.QLabel()
        main_layout.addWidget(self.jsonStatusLabel)
        # 每次选择变化时自动加载
        self.jsonSelectCombo.currentIndexChanged.connect(self.load_json_from_combo)
        # 初始化 JSON 列表
        self.update_json_list()
        
        # ...原有菜单、splitter 等部分保持不变...
        menu_bar = QtWidgets.QMenuBar()
        file_menu = menu_bar.addMenu("文件")
        open_action = QtWidgets.QAction("打开", self)
        open_action.triggered.connect(self.choose_other_json)
        save_action = QtWidgets.QAction("保存", self)
        save_action.triggered.connect(self.save_json)
        save_as_action = QtWidgets.QAction("另存为", self)
        save_as_action.triggered.connect(self.save_json_as)
        file_menu.addAction(open_action)
        file_menu.addAction(save_action)
        file_menu.addAction(save_as_action)
        main_layout.setMenuBar(menu_bar)
        # ...后续原有 UI 代码...
        splitter = QtWidgets.QSplitter()
        main_layout.addWidget(splitter)
        # ...其余代码不变...
        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        self.file_list_widget = QtWidgets.QListWidget()
        self.file_list_widget.currentItemChanged.connect(self.on_file_selected)
        left_layout.addWidget(QtWidgets.QLabel("文件名列表："))
        left_layout.addWidget(self.file_list_widget)
        file_button_layout = QtWidgets.QHBoxLayout()
        add_file_button = QtWidgets.QPushButton("添加文件名")
        add_file_button.clicked.connect(self.add_file)
        remove_file_button = QtWidgets.QPushButton("删除文件名")
        remove_file_button.clicked.connect(self.remove_file)
        file_button_layout.addWidget(add_file_button)
        file_button_layout.addWidget(remove_file_button)
        left_layout.addLayout(file_button_layout)
        self.preset_list_widget = QtWidgets.QListWidget()
        self.preset_list_widget.currentItemChanged.connect(self.on_preset_selected)
        left_layout.addWidget(QtWidgets.QLabel("预设列表："))
        left_layout.addWidget(self.preset_list_widget)
        preset_button_layout = QtWidgets.QHBoxLayout()
        # 保存预设按钮为实例属性，便于后续控制状态
        self.add_preset_button = QtWidgets.QPushButton("添加预设")
        self.add_preset_button.clicked.connect(self.add_preset)
        self.remove_preset_button = QtWidgets.QPushButton("删除预设")
        self.remove_preset_button.clicked.connect(self.remove_preset)
        preset_button_layout.addWidget(self.add_preset_button)
        preset_button_layout.addWidget(self.remove_preset_button)
        left_layout.addLayout(preset_button_layout)
        splitter.addWidget(left_widget)
        right_widget = QtWidgets.QWidget()
        self.right_layout = QtWidgets.QVBoxLayout(right_widget)
        self.preset_detail_widget = QtWidgets.QWidget()
        preset_form_layout = QtWidgets.QFormLayout(self.preset_detail_widget)
        self.export_modes_widget = QtWidgets.QWidget()
        export_modes_layout = QtWidgets.QVBoxLayout(self.export_modes_widget)
        self.fbx_group = QtWidgets.QGroupBox("FBX导出方式")
        fbx_layout = QtWidgets.QFormLayout()
        self.fbx_models_list = QtWidgets.QListWidget()
        fbx_models_button_layout = QtWidgets.QHBoxLayout()
        self.add_fbx_model_button = QtWidgets.QPushButton("添加模型")
        self.add_fbx_model_button.clicked.connect(self.add_fbx_model)
        self.remove_fbx_model_button = QtWidgets.QPushButton("移除模型")
        self.remove_fbx_model_button.clicked.connect(self.remove_fbx_model)
        self.replace_fbx_model_button = QtWidgets.QPushButton("替换模型")
        self.replace_fbx_model_button.clicked.connect(self.replace_fbx_model)
        fbx_models_button_layout.addWidget(self.add_fbx_model_button)
        fbx_models_button_layout.addWidget(self.remove_fbx_model_button)
        fbx_models_button_layout.addWidget(self.replace_fbx_model_button)
        self.fbx_name_edit = QtWidgets.QLineEdit()
        fbx_layout.addRow("导出的模型列表：", self.fbx_models_list)
        fbx_layout.addRow("", fbx_models_button_layout)
        fbx_layout.addRow("导出的FBX名称：", self.fbx_name_edit)
        self.fbx_group.setLayout(fbx_layout)
        export_modes_layout.addWidget(self.fbx_group)
        self.abc_group = QtWidgets.QGroupBox("ABC导出方式")
        abc_layout = QtWidgets.QFormLayout()
        self.abc_models_list = QtWidgets.QListWidget()
        abc_models_button_layout = QtWidgets.QHBoxLayout()
        self.add_abc_model_button = QtWidgets.QPushButton("添加模型")
        self.add_abc_model_button.clicked.connect(self.add_abc_model)
        self.remove_abc_model_button = QtWidgets.QPushButton("移除模型")
        self.remove_abc_model_button.clicked.connect(self.remove_abc_model)
        self.replace_abc_model_button = QtWidgets.QPushButton("替换模型")
        self.replace_abc_model_button.clicked.connect(self.replace_abc_model)
        abc_models_button_layout.addWidget(self.add_abc_model_button)
        abc_models_button_layout.addWidget(self.remove_abc_model_button)
        abc_models_button_layout.addWidget(self.replace_abc_model_button)
        self.abc_name_edit = QtWidgets.QLineEdit()
        abc_layout.addRow("导出的模型列表：", self.abc_models_list)
        abc_layout.addRow("", abc_models_button_layout)
        abc_layout.addRow("导出的ABC名称：", self.abc_name_edit)
        self.abc_group.setLayout(abc_layout)
        export_modes_layout.addWidget(self.abc_group)
        self.bake_checkbox = QtWidgets.QCheckBox("导出是否烘培")
        export_modes_layout.addWidget(self.bake_checkbox)
        self.exclude_models_list = QtWidgets.QListWidget()
        exclude_models_button_layout = QtWidgets.QHBoxLayout()
        self.add_exclude_model_button = QtWidgets.QPushButton("添加模型")
        self.add_exclude_model_button.clicked.connect(self.add_exclude_model)
        self.remove_exclude_model_button = QtWidgets.QPushButton("移除模型")
        self.remove_exclude_model_button.clicked.connect(self.remove_exclude_model)
        self.replace_exclude_model_button = QtWidgets.QPushButton("替换模型")
        self.replace_exclude_model_button.clicked.connect(self.replace_exclude_model)
        exclude_models_button_layout.addWidget(self.add_exclude_model_button)
        exclude_models_button_layout.addWidget(self.remove_exclude_model_button)
        exclude_models_button_layout.addWidget(self.replace_exclude_model_button)
        preset_form_layout.addRow("不导出的模型列表：", self.exclude_models_list)
        preset_form_layout.addRow("", exclude_models_button_layout)
        self.preset_detail_widget.setLayout(preset_form_layout)
        self.right_layout.addWidget(self.preset_detail_widget)
        self.right_layout.addWidget(self.export_modes_widget)
        splitter.addWidget(right_widget)
        save_changes_button = QtWidgets.QPushButton("保存更改")
        save_changes_button.clicked.connect(self.save_preset_changes)
        main_layout.addWidget(save_changes_button)

    # 新增方法：更新 JSON 文件列表
    def update_json_list(self):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        json_files = [f for f in os.listdir(dir_path) if f.endswith(".json")]
        self.jsonSelectCombo.clear()
        self.jsonSelectCombo.addItems(json_files)
        # 默认选中第一个
        if json_files:
            self.current_json_path = os.path.join(dir_path, json_files[0])
            self.update_status_panel()

    # 新增方法：根据 JSON 下拉框选项自动加载 JSON
    def load_json_from_combo(self):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        filename = self.jsonSelectCombo.currentText()
        if filename:
            self.current_json_path = os.path.join(dir_path, filename)
            self.load_json()
            self.update_status_panel()

    # 修改 load_json 方法：若 current_json_path 为空，则先尝试使用下拉框选择
    def load_json(self):
        if not self.current_json_path:
            # 未指定，则尝试使用下拉框当前选项
            dir_path = os.path.dirname(os.path.realpath(__file__))
            selected = self.jsonSelectCombo.currentText()
            if selected:
                self.current_json_path = os.path.join(dir_path, selected)
        if self.current_json_path and os.path.exists(self.current_json_path):
            with open(self.current_json_path, 'r', encoding='utf-8') as f:
                self.presets = json.load(f)
            self.update_file_list()
            self.update_status_panel(read_state="读取成功")
        else:
            self.presets = {}
            self.update_status_panel(read_state="读取失败")

    # 新增方法：通过文件对话框选择其他 JSON 文件
    def choose_other_json(self):
        json_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "打开JSON文件", "", "JSON Files (*.json)")
        if json_path:
            self.current_json_path = json_path
            self.load_json()
            self.update_status_panel()

    # 新增方法：更新状态区显示（显示 JSON 位置、文件名、读取状态、最后保存时间等）
    def update_status_panel(self, read_state=""):
        if self.current_json_path and os.path.exists(self.current_json_path):
            file_info = os.stat(self.current_json_path)
            saved_time = QtCore.QDateTime.fromSecsSinceEpoch(int(file_info.st_mtime)).toString("yyyy-MM-dd hh:mm:ss")
            status_text = (
                f"位置：{os.path.dirname(self.current_json_path)}  "
                f"文件名：{os.path.basename(self.current_json_path)}  "
                f"读取状态：{read_state}  "
                f"最后保存时间：{saved_time}"
            )
        else:
            status_text = "无 JSON 文件加载"
        self.jsonStatusLabel.setText(status_text)

    def save_json(self):
        if self.current_json_path:
            with open(self.current_json_path, 'w', encoding='utf-8') as f:
                json.dump(self.presets, f, ensure_ascii=False, indent=4)
        else:
            self.save_json_as()

    def save_json_as(self):
        json_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "另存为JSON文件", "", "JSON Files (*.json)")
        if json_path:
            self.current_json_path = json_path
            self.save_json()

    def update_file_list(self):
        self.file_list_widget.clear()
        self.file_list_widget.addItems(self.presets.keys())

    def on_file_selected(self, current, previous):
        self.preset_list_widget.clear()
        if current:
            filename = current.text()
            self.update_preset_list(filename)
            # 启用添加和删除预设按钮
            self.add_preset_button.setEnabled(True)
            self.remove_preset_button.setEnabled(True)
        else:
            # 没有选中的文件，则禁用预设操作
            self.add_preset_button.setEnabled(False)
            self.remove_preset_button.setEnabled(False)
            self.clear_preset_details()

    def update_preset_list(self, filename):
        self.preset_list_widget.clear()
        if filename in self.presets:
            self.preset_list_widget.addItems(self.presets[filename].keys())

    def on_preset_selected(self, current, previous):
        if current:
            preset_name = current.text()
            filename = self.file_list_widget.currentItem().text()
            self.update_preset_details(filename, preset_name)

    def update_preset_details(self, filename, preset_name):
        if filename in self.presets and preset_name in self.presets[filename]:
            preset = self.presets[filename][preset_name]
            self.fbx_name_edit.setText(preset.get('导出方式', {}).get('fbx', {}).get('导出的fbx名称', ''))
            self.abc_name_edit.setText(preset.get('导出方式', {}).get('abc', {}).get('导出的abc名称', ''))
            self.bake_checkbox.setChecked(preset.get('导出是否烘培', False))
            self.update_model_list(self.fbx_models_list, preset.get('导出方式', {}).get('fbx', {}).get('导出的模型', []))
            self.update_model_list(self.abc_models_list, preset.get('导出方式', {}).get('abc', {}).get('导出的模型', []))
            self.update_model_list(self.exclude_models_list, preset.get('不导出的模型', []))

    def update_model_list(self, list_widget, models):
        list_widget.clear()
        list_widget.addItems(models)

    def add_file(self):
        filename, ok = QtWidgets.QInputDialog.getText(self, "添加文件名", "文件名:")
        if ok and filename:
            self.presets[filename] = {}
            self.update_file_list()

    def remove_file(self):
        current_item = self.file_list_widget.currentItem()
        if current_item:
            filename = current_item.text()
            del self.presets[filename]
            self.update_file_list()

    def add_preset(self):
        current_item = self.file_list_widget.currentItem()
        if current_item:
            filename = current_item.text()
            preset_name, ok = QtWidgets.QInputDialog.getText(self, "添加预设", "预设名:")
            if ok and preset_name:
                self.presets[filename][preset_name] = {
                    "导出方式": {
                        "fbx": {
                            "导出的fbx名称": "",
                            "导出的模型": []
                        },
                        "abc": {
                            "导出的abc名称": "",
                            "导出的模型": []
                        }
                    },
                    "导出是否烘培": False,
                    "不导出的模型": []
                }
                self.update_preset_list(filename)

    def remove_preset(self):
        current_item = self.preset_list_widget.currentItem()
        if current_item:
            preset_name = current_item.text()
            filename = self.file_list_widget.currentItem().text()
            del self.presets[filename][preset_name]
            self.update_preset_list(filename)

    def add_fbx_model(self):
        self.add_model(self.fbx_models_list)

    def remove_fbx_model(self):
        self.remove_model(self.fbx_models_list)

    def replace_fbx_model(self):
        self.replace_model(self.fbx_models_list)

    def add_abc_model(self):
        self.add_model(self.abc_models_list)

    def remove_abc_model(self):
        self.remove_model(self.abc_models_list)

    def replace_abc_model(self):
        self.replace_model(self.abc_models_list)

    def add_exclude_model(self):
        self.add_model(self.exclude_models_list)

    def remove_exclude_model(self):
        self.remove_model(self.exclude_models_list)

    def replace_exclude_model(self):
        self.replace_model(self.exclude_models_list)

    # 修改 PresetManager 的 add_model 方法，直接添加场景中所选模型的名字
    def add_model(self, list_widget):
        import maya.cmds as cmds
        selection = cmds.ls(selection=True, long=False)
        if selection:
            for sel in selection:
                # 去除命名空间部分（若存在冒号则取最后部分）
                name = sel.split(':')[-1]
                list_widget.addItem(name)
        else:
            QtWidgets.QMessageBox.warning(self, "提示", "场景中未选择任何模型。")

    def remove_model(self, list_widget):
        current_item = list_widget.currentItem()
        if current_item:
            list_widget.takeItem(list_widget.row(current_item))

    def replace_model(self, list_widget):
        current_item = list_widget.currentItem()
        if current_item:
            model_name, ok = QtWidgets.QInputDialog.getText(self, "替换模型", "模型名:", text=current_item.text())
            if ok and model_name:
                current_item.setText(model_name)

    def save_preset_changes(self):
        # 保存右侧编辑的预设内容到当前选中的预设项
        current_file = self.file_list_widget.currentItem()
        current_preset = self.preset_list_widget.currentItem()
        if current_file and current_preset:
            filename = current_file.text()
            preset_name = current_preset.text()
            preset = self.presets.get(filename, {}).get(preset_name, {})
            export_mode = {}
            export_mode["fbx"] = {
                "导出的fbx名称": self.fbx_name_edit.text().strip(),
                "导出的模型": [self.fbx_models_list.item(i).text() for i in range(self.fbx_models_list.count())]
            }
            export_mode["abc"] = {
                "导出的abc名称": self.abc_name_edit.text().strip(),
                "导出的模型": [self.abc_models_list.item(i).text() for i in range(self.abc_models_list.count())]
            }
            preset["导出方式"] = export_mode
            preset["导出是否烘培"] = self.bake_checkbox.isChecked()
            preset["不导出的模型"] = [self.exclude_models_list.item(i).text() for i in range(self.exclude_models_list.count())]
            self.presets[filename][preset_name] = preset
            self.save_json()
            QtWidgets.QMessageBox.information(self, "保存成功", "预设已保存。")

    def clear_preset_details(self):
        # 清空右侧预设详情控件
        self.fbx_models_list.clear()
        self.fbx_name_edit.clear()
        self.abc_models_list.clear()
        self.abc_name_edit.clear()
        self.bake_checkbox.setChecked(False)
        self.exclude_models_list.clear()

# 运行工具
def show_export_tool():
    global export_tool_dialog
    try:
        export_tool_dialog.close()  # 如果已打开，则关闭现有对话框
    except:
        pass
    export_tool_dialog = ExportTool()
    export_tool_dialog.show()

def show_preset_manager():
    global preset_manager_dialog
    try:
        preset_manager_dialog.close()  # 如果已打开，则关闭现有对话框
    except:
        pass
    preset_manager_dialog = PresetManager()
    preset_manager_dialog.show()

# 每次打开时重新加载所有内容
def reload_and_show():
    import sys
    module_name = 'export_tool'
    if (module_name in sys.modules):
        import importlib
        mod = importlib.reload(sys.modules[module_name])
    else:
        import export_tool as mod
    mod.show_export_tool()

reload_and_show()
