# Copilot Skills 链接脚本

使用这两个脚本，可以只维护一份 Skills 源目录，并将 VS Code Copilot 的个人级目录链接到该目录。

默认目标目录：

- macOS/Linux：`~/.copilot/skills`
- Windows：`%USERPROFILE%\.copilot\skills`

源目录必须包含至少一个 `<skill-name>/SKILL.md`。

## macOS

首次赋予执行权限：

```sh
chmod +x scripts/link-copilot-skills.sh
```

建立链接：

```sh
./scripts/link-copilot-skills.sh "/Users/your-name/path/to/skills"
```

## Linux

```sh
chmod +x scripts/link-copilot-skills.sh
./scripts/link-copilot-skills.sh "/home/your-name/path/to/skills"
```

## Windows

在 PowerShell 中运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\link-copilot-skills.ps1 -Source "D:\path\to\skills"
```

Windows 默认创建目录 Junction，通常不要求管理员权限或开启开发者模式。如果希望创建真正的符号链接，可以使用：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\link-copilot-skills.ps1 -Source "D:\path\to\skills" -LinkType SymbolicLink
```

创建 SymbolicLink 可能需要开启 Windows 开发者模式或使用管理员终端。

## 常用参数

指定其他目标位置：

```sh
./scripts/link-copilot-skills.sh --target "/custom/copilot/skills" "/path/to/skills"
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\link-copilot-skills.ps1 -Source "D:\path\to\skills" -Target "D:\custom\copilot\skills"
```

如果目标已存在，脚本默认拒绝覆盖。显式使用 `--force`（macOS/Linux）或 `-Force`（Windows）时，旧目标会被重命名为带时间戳的备份，然后再创建链接：

```sh
./scripts/link-copilot-skills.sh --force "/path/to/skills"
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\link-copilot-skills.ps1 -Source "D:\path\to\skills" -Force
```

脚本可以安全地重复执行；如果目标已经链接到同一个源目录，会直接成功退出。

完成后，在 VS Code 中运行 **Developer: Reload Window**，并新建 Copilot Chat 会话。
