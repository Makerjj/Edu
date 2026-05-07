# 新东方学情反馈表生成工具

按团队名称、训练名称和题目列表，从 `code.xdf.cn` 拉取学生完成情况，并生成和参考模板风格一致的 Excel 学情反馈表。

## 环境准备

```bash
python3 -m venv .venv
.venv/bin/python -m pip install requests openpyxl pytest pypinyin
```

## 配置文件

复制 [config.example.json](config.example.json) 为 `config.json`，填写账号、密码、模板路径和默认输出目录。

```json
{
  "account": "你的手机号",
  "password": "你的密码",
  "template_path": "/Users/jm/Desktop/新东方/学情反馈表/周六一档易生活102-C1-3学情反馈表.xlsx",
  "output_dir": "./out"
}
```

如果 `account` 或 `password` 留空，程序会在运行时提示输入。

## 使用方式

```bash
.venv/bin/python xdf_report.py \
  --team "易生活102 C1" \
  --training "二分查找" \
  --problems "找苹果,字典找字,查找" \
  --after-class-problems "验证密码,逢7过"
```

也可以直接运行脚本：

```bash
./run_xdf_report.sh
```

如果要临时改团队、训练、题目和训练密码：

```bash
./run_xdf_report.sh "易生活102 C1" "二分查找" "找苹果,字典找字,查找" "1"
```

可选参数：

- `--config`：自定义配置文件路径，默认 `config.json`
- `--output`：输出目录，或直接指定一个 `.xlsx` 文件路径
- `--students-json`：显式指定学生列表 JSON 文件，只有指定时才使用该文件中的用户并按姓名排序
- `--after-class-problems`：课后题名称或题号列表，支持中英文逗号分隔
- `--training-password`：私有训练的训练密码；不传时会在需要时提示输入

示例：

```bash
.venv/bin/python xdf_report.py \
  --team "易生活102 C1" \
  --training "二分查找" \
  --problems "找苹果,字典找字,查找" \
  --after-class-problems "验证密码,逢7过" \
  --training-password "1" \
  --output "./out"
```

课后题解析规则：

- 先在当前训练里匹配 `--after-class-problems`
- 当前训练未命中时，再回退到上一训练匹配
- 某个课后题在两边都没匹配到时，会输出警告并跳过该题
- 如果最终没有可用课后题，Excel 的课后作业区域会保持空白

## 匹配规则

- 团队名称：包含匹配
- 团队参数也支持直接传团队 gid，例如 `2186`
- 团队参数也支持直接传团队链接，例如 `https://code.xdf.cn/oj/group/2186`
- 训练名称：包含匹配
- 题目：优先按题号精确匹配；未命中时按题目标题包含匹配
- 题目列表支持英文逗号 `,` 和中文逗号 `，`
- 当站点官方团队搜索接口异常时，工具会自动降级为 gid 扫描匹配可访问团队

## 输出说明

- 默认输出到配置里的 `output_dir`
- 若未显式指定文件名，文件名格式为：

```text
团队名_训练名_题目摘要_学情反馈表.xlsx
```

- 多题时会简写为 `首题名等N题`
- 程序成功后会在标准输出打印最终文件路径

## 测试

```bash
.venv/bin/python -m pytest tests -v
```
