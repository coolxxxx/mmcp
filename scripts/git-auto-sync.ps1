Param(
  [switch]$NonInteractive,     # 非交互模式：空提交信息将自动生成
  [switch]$VerboseLog          # 显示更多日志
)

$ErrorActionPreference = 'Stop'

function Write-Status {
  param([string]$Message, [ValidateSet('INFO','WARN','ERROR','OK')][string]$Level='INFO')
  $color = switch ($Level) {
    'INFO'  { 'Cyan' }
    'WARN'  { 'Yellow' }
    'ERROR' { 'Red' }
    'OK'    { 'Green' }
  }
  Write-Host "[$Level] $Message" -ForegroundColor $color
}

function Run-Git {
  param([string]$Args)
  if ($VerboseLog) { Write-Status "git $Args" 'INFO' }
  $output = git $Args 2>&1
  $code = $LASTEXITCODE
  return @{ Code = $code; Output = $output }
}

try {
  # 0) 依赖与位置校验
  if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Status "未找到 git 命令，请先安装 Git 并确保在 PATH 中。" 'ERROR'
    exit 1
  }

  $inside = Run-Git "rev-parse --is-inside-work-tree"
  if ($inside.Code -ne 0 -or ($inside.Output | Select-Object -First 1) -ne 'true') {
    Write-Status "当前目录不是一个 Git 仓库。" 'ERROR'
    exit 1
  }

  # 1) 当前分支
  $branchRes = Run-Git "rev-parse --abbrev-ref HEAD"
  if ($branchRes.Code -ne 0) {
    Write-Status "无法获取当前分支：`n$($branchRes.Output)" 'ERROR'
    exit 1
  }
  $branch = ($branchRes.Output | Select-Object -First 1).Trim()
  Write-Status "当前分支：$branch" 'INFO'

  # 2) 工作区是否干净
  $porcelain = Run-Git "status --porcelain"
  $dirty = -not [string]::IsNullOrWhiteSpace(($porcelain.Output -join "`n"))
  if ($dirty) {
    Write-Status "检测到未提交变更：" 'WARN'
    git -c color.status=always status -s

    $commitMsg = $null
    if ($NonInteractive) {
      $commitMsg = "chore: auto commit on $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
      Write-Status "非交互模式，将使用自动提交信息：$commitMsg" 'INFO'
    } else {
      $commitMsg = Read-Host "请输入提交信息（留空将自动生成）"
      if ([string]::IsNullOrWhiteSpace($commitMsg)) {
        $commitMsg = "chore: auto commit on $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        Write-Status "已采用自动提交信息：$commitMsg" 'INFO'
      }
    }

    $addRes = Run-Git "add -A"
    if ($addRes.Code -ne 0) {
      Write-Status "git add 失败：`n$($addRes.Output)" 'ERROR'
      exit 1
    }

    $commitRes = Run-Git "commit -m `"$commitMsg`""
    if ($commitRes.Code -ne 0) {
      # 若无实质变化（比如仅文件权限变化被忽略）
      if (($commitRes.Output -join "`n") -match 'nothing to commit|no changes added') {
        Write-Status "无可提交内容，跳过 commit。" 'WARN'
      } else {
        Write-Status "git commit 失败：`n$($commitRes.Output)" 'ERROR'
        exit 1
      }
    } else {
      Write-Status "提交完成。" 'OK'
    }
  } else {
    Write-Status "工作区干净，无未提交变更。" 'OK'
  }

  # 3) 上游分支检测
  $upstreamName = $null
  $upRes = Run-Git 'rev-parse --abbrev-ref --symbolic-full-name @{u}'
  if ($upRes.Code -eq 0) {
    $upstreamName = ($upRes.Output | Select-Object -First 1).Trim()
    Write-Status "已关联上游：$upstreamName" 'OK'
  } else {
    Write-Status "当前分支尚未关联上游分支。" 'WARN'
    # 检查是否存在 origin
    $remoteList = Run-Git "remote"
    $hasOrigin = ($remoteList.Output -join "`n") -split "`n" | Where-Object { $_.Trim() -eq 'origin' } | ForEach-Object { $_ } | Measure-Object | Select-Object -ExpandProperty Count
    if ($hasOrigin -gt 0) {
      Write-Status "检测到远程 origin，将在首次推送时创建并关联上游 (origin/$branch)。" 'INFO'
    } else {
      if ($NonInteractive) {
        Write-Status "非交互模式且未配置远程，无法继续推送。" 'ERROR'
        exit 2
      }
      $url = Read-Host "未检测到远程。请输入远程仓库 URL（例如 https://github.com/user/repo.git 或 git@github.com:user/repo.git）"
      if ([string]::IsNullOrWhiteSpace($url)) {
        Write-Status "未提供远程 URL，无法继续。" 'ERROR'
        exit 2
      }
      $addRemoteRes = Run-Git "remote add origin `"$url`""
      if ($addRemoteRes.Code -ne 0) {
        Write-Status "添加远程失败：`n$($addRemoteRes.Output)" 'ERROR'
        exit 2
      }
      Write-Status "已添加远程 origin：$url" 'OK'
    }
  }

  # 4) 展示未推送提交统计
  $aheadBehind = Run-Git 'rev-list --left-right --count @{u}...HEAD'
  if ($aheadBehind.Code -eq 0) {
    $parts = (($aheadBehind.Output | Select-Object -First 1).Trim() -split '\s+')
    if ($parts.Count -ge 2) {
      $behind = [int]$parts[0]; $ahead = [int]$parts[1]
      Write-Status "相对上游：ahead=$ahead, behind=$behind" 'INFO'
    }
  }

  # 5) 推送
  $pushCmd = if ($upstreamName) { "push" } else { "push -u origin `"$branch`"" }
  Write-Status "执行：git $pushCmd" 'INFO'
  $pushRes = Run-Git $pushCmd
  if ($pushRes.Code -eq 0) {
    Write-Status "推送成功。" 'OK'
    exit 0
  }

  # 6) 推送失败处理（常见为需先拉取）
  $pushOutput = $pushRes.Output -join "`n"
  Write-Status "推送失败：`n$pushOutput" 'ERROR'

  if ($pushOutput -match 'non-fast-forward|fetch first|Updates were rejected') {
    if ($NonInteractive) {
      Write-Status "检测到需要先拉取变更（非快进）。非交互模式下将自动执行：git pull --rebase --autostash，然后重试推送。" 'WARN'
      $auto = $true
    } else {
      $ans = Read-Host "检测到远端有更新。是否执行 git pull --rebase --autostash 并重试推送？(y/N)"
      $auto = ($ans -match '^(y|yes)$')
    }

    if ($auto) {
      $pullRes = Run-Git "pull --rebase --autostash"
      if ($pullRes.Code -ne 0) {
        Write-Status "拉取/变基失败：`n$($pullRes.Output -join "`n")" 'ERROR'
        Write-Status "请手动解决冲突后再次运行本脚本。" 'WARN'
        exit 3
      }
      Write-Status "拉取并变基完成，重试推送..." 'INFO'
      $pushRes2 = Run-Git $pushCmd
      if ($pushRes2.Code -eq 0) {
        Write-Status "推送成功。" 'OK'
        exit 0
      } else {
        Write-Status "重试推送仍失败：`n$($pushRes2.Output -join "`n")" 'ERROR'
        exit 4
      }
    } else {
      Write-Status "已取消自动处理。请先手动执行 git pull --rebase 后再推送。" 'WARN'
      exit 5
    }
  } else {
    Write-Status "未知推送错误，请检查上面输出或网络/认证状态。" 'ERROR'
    exit 6
  }

} catch {
  Write-Status "脚本异常：$($_.Exception.Message)" 'ERROR'
  exit 99
}