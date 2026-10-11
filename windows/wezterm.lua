-- Mike 的 PC WezTerm 設定：對齊 Mac 的 Ghostty + cmux（原檔見 mike-claude repo terminal/mac/）
-- 改完存檔 WezTerm 會自動重載
local wezterm = require 'wezterm'
local act = wezterm.action
local config = wezterm.config_builder()

-- Catppuccin Macchiato 色票
local mauve = '#c6a0f6'
local base = '#24273a'
local mantle = '#1e2030'
local crust = '#181926'
local surface0 = '#363a4f'
local text = '#cad3f5'
local subtext = '#a5adcb'

-- ── 外觀（ghostty.config / cmux-theme.ghostty）─────────────
config.font = wezterm.font_with_fallback {
  'JetBrainsMono Nerd Font',
  'JetBrains Mono', -- WezTerm 內建，Nerd Font 沒裝時的退路
  'Microsoft JhengHei', -- 中文 fallback（Mac 是 PingFang TC）
}
config.font_size = 12 -- Mac 是 12 × cmux 全域 120%；看了再調
config.line_height = 1.15 -- adjust-cell-height = 15%
config.cursor_blink_rate = 0 -- 關閉游標閃爍（Claude Code 會要求閃爍游標，預設 800ms 太刺眼）
config.color_scheme = 'Catppuccin Macchiato'
config.colors = {
  background = mantle, -- Macchiato 深一階
  split = mauve, -- 分割線用 mauve（cmux activePaneBorderColor）
  tab_bar = {
    background = crust,
    active_tab = { bg_color = mauve, fg_color = crust, intensity = 'Bold' },
    inactive_tab = { bg_color = crust, fg_color = subtext },
    inactive_tab_hover = { bg_color = surface0, fg_color = text },
    new_tab = { bg_color = crust, fg_color = subtext },
    new_tab_hover = { bg_color = surface0, fg_color = text },
  },
}
config.window_background_opacity = 0.85
config.win32_system_backdrop = 'Acrylic' -- background-blur
config.inactive_pane_hsb = { saturation = 0.85, brightness = 0.65 } -- 非聚焦 pane 變暗
config.window_padding = { left = 8, right = 8, top = 6, bottom = 4 }
config.window_decorations = 'INTEGRATED_BUTTONS|RESIZE'
config.use_fancy_tab_bar = false
config.tab_bar_at_bottom = false
config.tab_max_width = 32
config.show_new_tab_button_in_tab_bar = false
config.initial_cols = 160
config.initial_rows = 44
config.use_ime = true -- 注音
config.audible_bell = 'Disabled'
config.scrollback_lines = 20000

-- ── Shell ──────────────────────────────────────────────
config.default_prog = { 'powershell.exe', '-NoLogo' }
local claude_prog = { 'powershell.exe', '-NoLogo', '-NoExit', '-Command', 'claude' }

-- ── 分頁列左側顯示 workspace（cmux sidebar 的替代）─────────
wezterm.on('update-status', function(window, pane)
  local leader = window:leader_is_active() and ' LEADER ' or ''
  window:set_left_status(wezterm.format {
    { Background = { Color = mauve } },
    { Foreground = { Color = crust } },
    { Attribute = { Intensity = 'Bold' } },
    { Text = ' ' .. window:active_workspace() .. ' ' },
    'ResetAttributes',
    { Background = { Color = '#f5a97f' } },
    { Foreground = { Color = crust } },
    { Text = leader },
    'ResetAttributes',
    { Text = ' ' },
  })
end)

-- ── 鍵位：leader = Ctrl+a（tmux 手感）─────────────────────
config.leader = { key = 'a', mods = 'CTRL', timeout_milliseconds = 1500 }
config.keys = {
  -- leader 再按一次 Ctrl+a 送出原本的 Ctrl+a（PowerShell 行首）
  { key = 'a', mods = 'LEADER|CTRL', action = act.SendKey { key = 'a', mods = 'CTRL' } },

  -- 分割 / 放大 / 關閉
  { key = '|', mods = 'LEADER|SHIFT', action = act.SplitHorizontal { domain = 'CurrentPaneDomain' } },
  { key = '\\', mods = 'LEADER', action = act.SplitHorizontal { domain = 'CurrentPaneDomain' } },
  { key = '-', mods = 'LEADER', action = act.SplitVertical { domain = 'CurrentPaneDomain' } },
  { key = 'z', mods = 'LEADER', action = act.TogglePaneZoomState },
  { key = 'x', mods = 'LEADER', action = act.CloseCurrentPane { confirm = true } },

  -- 切 pane（leader + 方向鍵 / hjkl）
  { key = 'LeftArrow', mods = 'LEADER', action = act.ActivatePaneDirection 'Left' },
  { key = 'RightArrow', mods = 'LEADER', action = act.ActivatePaneDirection 'Right' },
  { key = 'UpArrow', mods = 'LEADER', action = act.ActivatePaneDirection 'Up' },
  { key = 'DownArrow', mods = 'LEADER', action = act.ActivatePaneDirection 'Down' },
  { key = 'h', mods = 'LEADER', action = act.ActivatePaneDirection 'Left' },
  { key = 'l', mods = 'LEADER', action = act.ActivatePaneDirection 'Right' },
  { key = 'k', mods = 'LEADER', action = act.ActivatePaneDirection 'Up' },
  { key = 'j', mods = 'LEADER', action = act.ActivatePaneDirection 'Down' },
  -- 調整 pane 大小（Alt + 方向鍵，免 leader 方便連按）
  { key = 'LeftArrow', mods = 'ALT|SHIFT', action = act.AdjustPaneSize { 'Left', 5 } },
  { key = 'RightArrow', mods = 'ALT|SHIFT', action = act.AdjustPaneSize { 'Right', 5 } },
  { key = 'UpArrow', mods = 'ALT|SHIFT', action = act.AdjustPaneSize { 'Up', 3 } },
  { key = 'DownArrow', mods = 'ALT|SHIFT', action = act.AdjustPaneSize { 'Down', 3 } },

  -- 分頁
  { key = 'c', mods = 'LEADER', action = act.SpawnTab 'CurrentPaneDomain' },
  { key = 'n', mods = 'LEADER|SHIFT', action = act.ActivateTabRelative(1) },
  { key = 'p', mods = 'LEADER', action = act.ActivateTabRelative(-1) },

  -- Workspace：一個 workspace＝一個任務（cmux 習慣）
  { key = 'w', mods = 'LEADER', action = act.ShowLauncherArgs { flags = 'FUZZY|WORKSPACES' } },
  {
    key = 'n',
    mods = 'LEADER',
    action = act.PromptInputLine {
      description = wezterm.format {
        { Attribute = { Intensity = 'Bold' } },
        { Foreground = { Color = mauve } },
        { Text = '新 workspace 名稱（會直接啟動 claude）：' },
      },
      action = wezterm.action_callback(function(window, pane, line)
        if line and line ~= '' then
          window:perform_action(act.SwitchToWorkspace { name = line, spawn = { args = claude_prog } }, pane)
        end
      end),
    },
  },
  -- 在目前 workspace 右側開一個 claude pane（並排看 agent）
  {
    key = 'C',
    mods = 'LEADER|SHIFT',
    action = act.SplitPane { direction = 'Right', command = { args = claude_prog } },
  },
  { key = '$', mods = 'LEADER|SHIFT', action = act.PromptInputLine {
      description = '重新命名 workspace：',
      action = wezterm.action_callback(function(window, pane, line)
        if line and line ~= '' then
          wezterm.mux.rename_workspace(wezterm.mux.get_active_workspace(), line)
        end
      end),
    },
  },
  { key = '[', mods = 'LEADER', action = act.ActivateCopyMode },
}

-- 啟動時的 workspace 名稱
config.default_workspace = 'main'

return config
