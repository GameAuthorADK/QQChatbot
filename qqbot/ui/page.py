INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>QQChatbot</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  html, body { height: 100%; }
  body { margin:0; font:14px/1.55 "Segoe UI","Microsoft YaHei",sans-serif;
         background:#14161a; color:#e6e8eb; display:flex; flex-direction:column; }

  header { padding:12px 18px; border-bottom:1px solid #262a31;
           display:flex; align-items:center; gap:10px; flex:0 0 auto; }
  header h1 { font-size:14px; margin:0; font-weight:600; letter-spacing:.4px; }
  .dot { width:9px; height:9px; border-radius:50%; background:#666; }
  .dot.ready { background:#2ecc71; box-shadow:0 0 8px #2ecc7155; }
  .dot.warn { background:#f1c40f; }
  .dot.err { background:#e74c3c; }

  .shell { display:flex; flex:1 1 auto; min-height:0; }

  aside { width:168px; flex:0 0 auto; border-right:1px solid #262a31;
          padding:10px 8px; display:flex; flex-direction:column; gap:2px; }
  aside .navmain { display:flex; flex-direction:column; gap:2px; }
  aside button { text-align:left; background:transparent; color:#9aa3b2;
                 border:0; padding:9px 12px; border-radius:8px; cursor:pointer;
                 font:inherit; }
  aside button:hover { background:#1c1f25; color:#e6e8eb; }
  aside button.active { background:#23304a; color:#fff; font-weight:600; }
  aside .asidefoot { margin-top:auto; padding:12px 6px 2px; border-top:1px solid #22262d;
                     display:flex; gap:8px; align-items:center; font-size:11px; }
  aside .asidefoot a { color:#666e7c; cursor:pointer; padding:2px 1px; }
  aside .asidefoot a:hover { color:#cfd6e2; }
  aside .asidefoot a.active { color:#7fb0ff; }
  aside .asidefoot .sep { color:#333a45; }

  main { flex:1 1 auto; overflow:auto; padding:18px 20px 40px; min-width:0; }

  .panel { display:none; }
  .panel.active { display:block; }
  .panel h2 { font-size:13px; color:#8b93a1; font-weight:600; margin:0 0 12px;
              text-transform:uppercase; letter-spacing:.8px; }

  section { background:#1b1e24; border:1px solid #262a31; border-radius:10px;
            padding:16px; margin-bottom:16px; }

  label { display:block; font-size:12px; color:#8b93a1; margin:10px 0 4px; }
  input, select, textarea { width:100%; padding:8px 10px; background:#0f1115;
          color:#e6e8eb; border:1px solid #2c313a; border-radius:6px; font:inherit; }
  textarea { resize:vertical; min-height:88px; font-family:inherit; }
  button { padding:8px 14px; background:#2d6cdf; color:#fff; border:0;
           border-radius:6px; font:inherit; cursor:pointer; }
  button.ghost { background:#2a2f38; }
  button.mini { padding:4px 10px; font-size:12px; }
  a.mini {
    display:inline-block; padding:4px 10px; font-size:12px; border-radius:6px;
    background:#1f242c; border:1px solid #2c3440; color:#dfe6ef;
    text-decoration:none; white-space:nowrap;
  }
  a.mini:hover { background:#28303b; }
  select.mini-sel { width:auto; padding:4px 8px; font-size:12px; }
  button:disabled { opacity:.45; cursor:default; }

  .row { display:flex; gap:8px; margin-top:14px; flex-wrap:wrap; align-items:center; }
  .grid2 { display:grid; grid-template-columns:1fr 1fr; gap:12px 18px; }
  .kv { display:grid; grid-template-columns:110px 1fr; gap:5px 10px; font-size:13px; }
  .kv div:nth-child(odd) { color:#8b93a1; }
  .hint { font-size:12px; color:#6b7382; }
  .field .hint { display:block; margin-top:4px; line-height:1.35; }
  .ok { color:#2ecc71; } .bad { color:#e74c3c; }

  pre { margin:0; background:#0f1115; border:1px solid #262a31; border-radius:6px;
        padding:10px; font-size:12px; white-space:pre-wrap; overflow:auto; }
  pre.log { height:260px; }
  pre.flow { line-height:1.75; font-family:"Consolas","Microsoft YaHei",monospace; }

  /* 帮助文档：直接排版，不套代码框 */
  .docwrap { max-width:900px; }
  .docnav { display:flex; flex-wrap:wrap; gap:16px; font-size:12px;
            margin-bottom:20px; padding-bottom:10px; border-bottom:1px solid #22262d; }
  .docnav a { color:#6b7382; cursor:pointer; padding-bottom:2px; }
  .docnav a:hover { color:#cfd6e2; }
  .docnav a.active { color:#e6e8eb; border-bottom:1px solid #2d6cdf; }
  .doc { font-size:13px; line-height:1.85; color:#d5dae2; word-wrap:break-word; }
  .doc h1 { font-size:20px; line-height:1.4; margin:0 0 16px; color:#fff;
            font-weight:600; letter-spacing:.2px; }
  .doc h2 { font-size:15px; margin:28px 0 10px; color:#e6e8eb; text-transform:none;
            letter-spacing:0; font-weight:600; }
  .doc h3 { font-size:13.5px; margin:20px 0 8px; color:#c3cbd7; font-weight:600; }
  .doc p { margin:0 0 10px; }
  .doc ul, .doc ol { margin:0 0 12px; padding-left:20px; }
  .doc li { margin:3px 0; }
  .doc li > ul, .doc li > ol { margin:4px 0; }
  .doc hr { border:0; border-top:1px solid #242932; margin:22px 0; }
  .doc code { background:#20242b; padding:1px 5px; border-radius:4px; font-size:12px;
              font-family:Consolas,"Microsoft YaHei",monospace; color:#e2e9f3; }
  .doc pre { background:#101318; border:1px solid #242932; border-radius:6px;
             padding:10px 12px; overflow:auto; margin:0 0 14px; white-space:pre; }
  .doc pre code { background:none; padding:0; font-size:12px; line-height:1.6;
                  white-space:pre; }
  .doc table { border-collapse:collapse; width:100%; margin:0 0 14px; font-size:12.5px; }
  .doc th, .doc td { border:1px solid #262c35; padding:6px 9px; text-align:left;
                     vertical-align:top; word-break:break-word; }
  .doc th:first-child, .doc td:first-child { width:1%; white-space:nowrap; }
  .doc th { background:#1b1f26; color:#aab3c0; font-weight:600; }
  .doc blockquote { margin:0 0 12px; padding:7px 12px; border-left:3px solid #2d6cdf;
                    background:#181c22; color:#a9b2c0; }
  .doc a { color:#7fb0ff; }
  .grp { margin-bottom:18px; }
  .fields2 { display:grid; grid-template-columns:1fr 1fr; gap:14px 20px; }

  .memrow { display:flex; align-items:center; gap:16px; flex-wrap:wrap; }
  .chk { display:flex; align-items:center; gap:8px; margin:0; font-size:13px;
         color:#e6e8eb; white-space:nowrap; }
  .chk input { width:auto; }
  .visionrow { margin-top:12px; padding:10px 12px; border:1px solid #262a31;
               border-radius:8px; background:#191c22; display:flex;
               flex-direction:column; gap:4px; }
  .visionrow .chk { margin:0; }
  .memth { display:flex; align-items:center; gap:6px; font-size:12px; color:#8b93a1; }
  .memth input { width:110px; }
  .membar { display:flex; align-items:center; justify-content:space-between;
            margin:18px 0 10px; padding-top:14px; border-top:1px solid #262a31; }
  .membar h3 { margin:0; font-size:12px; color:#8b93a1; font-weight:600; }
  .memlist { border:1px solid #262a31; border-radius:8px; background:#17191f;
             overflow:hidden; }
  .memitem { padding:10px 12px; border-bottom:1px solid #22262d; }
  .memitem:last-child { border-bottom:0; }
  .memrow2 { display:flex; align-items:center; gap:8px; margin-bottom:6px; }
  .memtextrow { display:flex; align-items:flex-start; gap:8px; }
  .memtextrow .memtext { flex:1; min-width:0; margin-top:0; }
  .memactions { display:flex; align-items:flex-start; gap:4px; flex-wrap:wrap;
                justify-content:flex-end; flex-shrink:0; }
  .pager { display:flex; align-items:center; gap:8px; margin-top:10px; }
  .memtext { white-space:pre-wrap; font-size:13px; line-height:1.65; margin-top:6px; }

  .chatwrap { display:flex; flex-direction:column; height:calc(100vh - 132px); min-height:420px; }
  .chatlog { flex:1 1 auto; overflow:auto; padding:16px; background:#1b1e24;
             border:1px solid #262a31; border-radius:10px;
             display:flex; flex-direction:column; gap:12px; }

  .line { display:flex; flex-direction:column; max-width:78%; }
  .line.user { align-self:flex-end; align-items:flex-end; }
  .line.bot { align-self:flex-start; align-items:flex-start; }
  .who { font-size:11px; color:#6b7382; margin-bottom:4px; padding:0 4px; letter-spacing:.3px; }

  .msg { max-width:100%; padding:9px 13px; border-radius:10px; font-size:13px;
         line-height:1.6; white-space:pre-wrap; word-break:break-word; }
  .msg.user { background:#2d6cdf; color:#fff; border-bottom-right-radius:3px; }
  .msg.bot  { background:#262a31; color:#e6e8eb; border-bottom-left-radius:3px; }
  .msg.sys  { align-self:center; background:transparent; color:#6b7382;
              font-size:12px; padding:2px 8px; max-width:100%; }

  .chatinput { display:flex; flex-direction:row; flex-wrap:nowrap;
               align-items:center; gap:8px; margin-top:12px; flex:0 0 auto; }
  .chatinput input { flex:1 1 auto; width:auto; min-width:0; }
  .chatinput button { flex:0 0 auto; width:auto; }

  .grow { display:flex; align-items:center; gap:8px; padding:8px 0;
          border-bottom:1px solid #22262d; flex-wrap:wrap; }
  .grow:last-child { border-bottom:0; }
  .tag { font-size:11px; padding:2px 8px; border-radius:999px; }
  .tag.active { background:#12331f; color:#2ecc71; }
  .tag.pending { background:#3a2f0d; color:#f1c40f; }
  .tag.disabled { background:#2a2f38; color:#8b93a1; }
  .tag.removed { background:#331414; color:#e74c3c; }
  .tag.muted { background:#331414; color:#e74c3c; }
  .tag.mode { background:#22314a; color:#7fb0ff; }

  .safety { border:1px solid #3a2f0d; background:#1d1a10; }
  .safety h2 { color:#f1c40f; }
</style>
</head>
<body>

<header>
  <div class="dot" id="dot"></div>
  <h1>QQChatbot</h1>
  <span id="stateText" class="hint">连接中…</span>
  <span style="flex:1"></span>
  <span id="inst" class="hint"></span>
</header>

<div class="shell">
  <aside>
    <div class="navmain">
      <button data-tab="basic" class="active">基础设置</button>
      <button data-tab="persona">人设 / 提示词</button>
      <button data-tab="global">全局回复设置</button>
      <button data-tab="reply">分群回复设置</button>
      <button data-tab="groups">群聊与黑名单</button>
      <button data-tab="chat">试聊窗口</button>
      <button data-tab="plugins">模式与插件</button>
    </div>
    <div class="asidefoot">
      <a data-doc="help">使用帮助</a>
      <span class="sep">|</span>
      <a data-doc="changelog">历史版本</a>
    </div>
  </aside>

  <main>
    <!-- ============ 基础设置 ============ -->
    <div class="panel active" id="tab-basic">
      <section>
        <h2>机器人凭据</h2>
        <div class="grid2">
          <div class="field">
            <label>AppID</label>
            <input id="appId" placeholder="开放平台「开发设置」里获取" autocomplete="off">
          </div>
          <div class="field">
            <label>AppSecret</label>
            <input id="appSecret" type="password" placeholder="留空表示不修改" autocomplete="off">
            <span class="hint">DPAPI 加密保存在本机，换机器需重新填写。</span>
          </div>
        </div>
        <div class="row">
          <button id="saveCred">保存并连接</button>
          <button class="ghost" id="disconnect">断开</button>
          <button class="ghost" id="pause">暂停接收</button>
        </div>
      </section>

      <section>
        <h2>模型</h2>
        <div class="grid2">
          <div class="field">
            <label>服务</label>
            <select id="pvKind"></select>
            <span id="pvNote" class="hint"></span>
          </div>
          <div class="field" id="pvModelWrap">
            <label>模型名</label>
            <div style="display:flex;gap:8px;flex-wrap:wrap">
              <select id="pvModelPick" class="mini-sel" style="max-width:240px"></select>
              <input id="pvModel" placeholder="选择或直接填写" style="flex:1;min-width:180px">
              <button class="ghost mini" id="pvFetchModels">拉取</button>
            </div>
            <span class="hint">先在左边列表里选，或直接在右边手写。</span>
          </div>
          <div class="field" id="pvKeyWrap">
            <label>API Key</label>
            <input id="pvKey" type="password" placeholder="留空表示不修改" autocomplete="off">
            <span class="hint">每个服务单独保存，切换服务不会互相覆盖。</span>
          </div>
          <div class="field">
            <label>超时（秒）</label>
            <input id="pvTimeout" type="number" min="5" max="60" step="1">
            <span class="hint">超时后改发兜底话术。群被动回复窗口是 5 分钟。</span>
          </div>
          <div class="field" id="pvBaseWrap" style="display:none;grid-column:1 / -1">
            <label>Base URL</label>
            <input id="pvBase" placeholder="https://your-endpoint/v1">
            <span class="hint">仅「自定义」需要填写；内置服务自动使用官方地址。</span>
          </div>
        </div>

        <div class="visionrow">
          <label class="chk"><input id="visionOn" type="checkbox">
            允许模型看图片</label>
          <span class="hint">
            模型必须支持图片输入（OpenAI 兼容的 image_url）。
            开启后 @bot 发图，文字和图片会一起交给模型；单张上限 4 MB，最多 3 张。
            关闭时只回一句「看不了图片」。
          </span>
        </div>
        <div class="row">
          <button id="pvSave">保存模型</button>
          <button class="ghost" id="pvTest">测试连通</button>
          <button class="ghost" id="visionTest">测试看图</button>
          <span id="pvStatus" class="hint"></span>
        </div>
      </section>

      <section>
        <h2>窗口</h2>
        <div class="fields2">
          <div class="field" style="grid-column:1 / -1">
            <label>点窗口 X 时</label>
            <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
              <select id="winCloseAction" style="flex:0 0 260px">
                <option value="tray">最小化到托盘（默认）</option>
                <option value="exit">退出程序</option>
              </select>
              <button id="winSave">保存窗口设置</button>
              <span id="winMsg" class="hint"></span>
            </div>
            <span class="hint">标题栏的最小化按钮和任务栏按钮仍然只最小化到底栏。</span>
          </div>
        </div>
      </section>

      <section>
        <h2>数据备份</h2>
        <p class="hint">
          备份包含数据库、人设和插件；不包含 AppSecret、模型 Key 等密钥。
          恢复后建议重启程序。
        </p>
        <div class="row">
          <a class="mini" id="backupBtn" href="/api/backup" download>下载备份</a>
          <button class="ghost" id="restoreBtn">恢复备份</button>
          <button class="ghost" id="resetData">清空业务数据</button>
          <input type="file" id="restoreFile" accept=".zip" style="display:none">
          <span id="dataMsg" class="hint"></span>
        </div>
      </section>

      <section>
        <h2>日志（已脱敏）</h2>
        <pre class="log" id="logs">加载中…</pre>
        <div class="row">
          <button class="ghost" id="diag">导出诊断包</button>
          <button class="ghost" id="logClear">清空日志</button>
          <button class="ghost" id="auditPrune">清理审计记录</button>
          <span id="logMsg" class="hint"></span>
        </div>
        <p class="hint" id="auditInfo">审计记录：加载中…</p>
      </section>
    </div>

    <!-- ============ 人设 / 提示词 ============ -->
    <div class="panel" id="tab-persona">
      <section>
        <h2>机器人设定</h2>
        <div class="field">
          <label>名字</label>
          <input id="psName" maxlength="40" placeholder="例如：小助手">
          <span class="hint">群里 @ 它或叫这个名字时，它知道在叫自己。</span>
        </div>
        <div class="field" style="margin-top:12px">
          <label>人设</label>
          <textarea id="psPersona" rows="5" maxlength="2000"
            placeholder="描述它的性格、说话方式、擅长什么。"></textarea>
          <span class="hint">建议 100–500 字。写得越具体，回答越稳定。上限 2000 字。</span>
        </div>
        <div class="field" style="margin-top:12px">
          <label>禁止事项（负面提示词）</label>
          <textarea id="psNegative" rows="4" maxlength="1000"
            placeholder="不希望它做的事，例如：不要用颜文字、不要问用户在做什么。"></textarea>
          <span class="hint">只写“不要做什么”。上限 1000 字。</span>
        </div>
        <div class="field" style="margin-top:12px">
          <label>回复风格</label>
          <textarea id="psStyle" rows="4" maxlength="800"
            placeholder="例如：像朋友聊天，句子短一点，偶尔吐槽，不用敬语。"></textarea>
          <span class="hint">单独规定说话风格、语气、长短，会拼在人设之后。上限 800 字。</span>
        </div>
        <div class="row">
          <button id="psSave">保存人设</button>
          <button class="ghost" id="psExport">导出人设</button>
          <button class="ghost" id="psImportBtn">导入人设</button>
          <input id="psImport" type="file" accept=".json,application/json" style="display:none">
          <span id="psMsg" class="hint"></span>
        </div>
      </section>

      <section>
        <h2>人设稳定</h2>
        <label class="chk"><input id="pgOn" type="checkbox"> 启用人设稳定</label>
        <p class="hint" style="margin-top:6px">
          每轮固定注入人设锚点；按群累计若干轮后让模型检查最近回复是否跑偏，并记录自检报告。
          主动发言也会计入轮数。下方可以随时手动自检。
        </p>
        <div id="personaFields" style="margin-top:10px">
          <div class="field">
            <label>人设锚点</label>
            <textarea id="pgAnchor" rows="5" maxlength="1000"
              placeholder="写最核心的身份、语气和禁忌，每轮都会固定注入。"></textarea>
            <span class="hint">
              建议 50–300 字，只写不能变的部分。启用后每轮都会拼在人设后面。上限 1000 字。
            </span>
          </div>
          <div class="field">
            <label>每多少条机器人回复自检</label>
            <input id="pgCheck" type="number" min="0" max="200" step="5">
            <span class="hint">
              按群累计机器人自己的回复和主动发言；达到后在下一次回复时更新报告。
              0 表示只做固定锚点，不自动更新报告。
            </span>
          </div>

          <label class="chk" style="margin-top:10px">
            <input id="pgUseModel" type="checkbox"> 启用额外自检模型
          </label>
          <span class="hint">不开启时，人设自检默认使用主模型。</span>
          <div id="pgModelBox" style="display:none;margin-top:10px">
            <div class="grid2">
              <div class="field">
                <label>服务</label>
                <select id="pgKind"></select>
                <span id="pgNote" class="hint"></span>
              </div>
              <div id="pgExtraFields" style="display:contents">
                <div class="field" id="pgModelWrap">
                  <label>模型名</label>
                  <div style="display:flex;gap:8px;flex-wrap:wrap">
                    <select id="pgModelPick" class="mini-sel" style="max-width:240px"></select>
                    <input id="pgModel" placeholder="选择或直接填写" style="flex:1;min-width:180px">
                    <button class="ghost mini" id="pgFetchModels">拉取</button>
                  </div>
                  <span class="hint">先在左边列表里选，或直接在右边手写。</span>
                </div>
                <div class="field">
                  <label>API Key</label>
                  <input id="pgKey" type="password" maxlength="300"
                    placeholder="留空沿用主模型 Key" autocomplete="off">
                  <span id="pgKeyHint" class="hint"></span>
                </div>
                <div class="field" id="pgBaseWrap" style="display:none;grid-column:1 / -1">
                  <label>Base URL</label>
                  <input id="pgBase" maxlength="300" placeholder="https://your-endpoint/v1">
                  <span class="hint">仅「自定义」需要填写；内置服务自动使用官方地址。</span>
                </div>
                <div class="row" style="grid-column:1 / -1">
                  <button class="ghost mini" id="pgCopy">参考主模型</button>
                  <span class="hint">只复制服务商、地址和模型名，不复制 Key。</span>
                </div>
              </div>
            </div>
          </div>

          <div class="row">
            <button id="pgSave">保存设置</button>
            <button class="ghost" id="pgPromptExport">导出提示词</button>
            <button class="ghost" id="pgPromptImportBtn">导入提示词</button>
            <input id="pgPromptImport" type="file" accept=".json,application/json" style="display:none">
            <span id="pgMsg" class="hint"></span>
          </div>
        </div>

        <div class="membar" style="margin-top:16px">
          <h3>自检报告</h3>
          <div style="display:flex;align-items:center;gap:8px">
            <button class="ghost mini" id="pgCheckNow">立即自检</button>
            <span id="pgReportsFileMsg" class="hint"></span>
            <button class="ghost mini" id="pgReportsExport">导出自检</button>
            <select id="pgReportsImportMode" class="mini-sel" style="max-width:120px">
              <option value="merge">合并追加</option>
              <option value="replace">覆盖全部</option>
            </select>
            <button class="ghost mini" id="pgReportsImportBtn">导入自检</button>
            <input id="pgReportsImport" type="file" accept=".json,application/json" style="display:none">
          </div>
        </div>
        <div id="pgReportsMsg" class="hint" style="margin-bottom:6px"></div>
        <div class="hint" style="margin-bottom:6px">只记录聊天模式；报告可以多行，每行“- 内容（权重）”，括号缺失或数值不合法时该行不生效；每群最多 10 条问题内容，0.0 不占名额，最新一条始终保留。</div>
        <div id="pgCheckMsg" class="hint" style="margin-bottom:6px"></div>
        <div id="pgReports"></div>
        <div id="pgReportsPager" class="pager"></div>
      </section>

      <section>
        <h2>记忆</h2>
        <div class="memrow">
          <label class="chk"><input id="memAuto" type="checkbox"> 自动总结对话</label>
          <div class="memth">
            整理阈值
            <input id="memTrigger" type="number" min="2000" max="32000" step="500">
            token
          </div>
          <div class="memth">
            或攒够
            <input id="memTriggerMsgs" type="number" min="10" max="500" step="10">
            条
          </div>
          <button id="memSave">保存</button>
          <span id="memMsg" class="hint"></span>
        </div>
        <p id="memCalc" class="hint" style="margin:10px 0 0"></p>
        <p id="memPending" class="hint" style="margin:4px 0 0"></p>
        <div class="row" style="margin:8px 0 0">
          <button class="ghost mini" id="memSummarize">立即整理</button>
          <span id="memSumMsg" class="hint"></span>
        </div>

        <div class="membar">
          <h3>已生成的记忆（按人隔离，可编辑）</h3>
          <div style="display:flex;align-items:center;gap:8px">
            <span id="memFileMsg" class="hint"></span>
            <button class="ghost mini" id="memExport">导出</button>
            <button class="ghost mini" id="memImportBtn">导入</button>
            <input id="memImport" type="file" accept=".json,application/json" style="display:none">
          </div>
        </div>
        <div id="memList"></div>
        <div id="memPager" class="pager"></div>
      </section>
    </div>

    <!-- ============ 全局回复设置 ============ -->
    <div class="panel" id="tab-global">
      <section>
        <h2>全局回复行为</h2>
        <div class="field">
          <label>默认兜底话术</label>
          <input id="gFallback" maxlength="200" placeholder="模型超时或失败时发这句">
          <span class="hint">模型超时、报错、额度耗尽时使用。建议短、不暴露内部错误。</span>
        </div>
        <div class="grid2" style="margin-top:12px">
          <div class="field">
            <label>默认单条字数上限</label>
            <input id="gChunk" type="number" min="200" max="4000" step="100">
            <span class="hint">超过就拆分。QQ 单条消息太长阅读体验差。</span>
          </div>
          <div class="field">
            <label>默认最多分几条</label>
            <input id="gChunks" type="number" min="1" max="5" step="1">
            <span class="hint">群被动回复每轮最多 5 次，默认 3 条留余量。</span>
          </div>
        </div>
        <div class="visionrow" style="margin-top:12px">
          <label class="chk"><input id="gMulti" type="checkbox"> 默认分条发送消息</label>
          <span class="hint">按句号、问号、感叹号或空行拆成几条短消息，句号会被去掉，问号和感叹号保留。</span>
          <div class="grid2" style="margin-top:8px">
            <div class="field">
              <label>最多几条</label>
              <input id="gMultiMax" type="number" min="1" max="5" step="1">
            </div>
            <div class="field">
              <label>每条间隔（毫秒）</label>
              <input id="gMultiDelay" type="number" min="0" max="5000" step="100">
            </div>
          </div>
        </div>
        <label class="chk" style="margin-top:10px;white-space:normal">
          <input id="gNoAt" type="checkbox">
          默认回复时不 @ 用户（改用主动消息，需要群开启「机器人主动发言」）
        </label>
        <div class="row">
          <button id="gReplySave">保存全局回复</button>
          <button class="ghost" id="gReplyExport">导出</button>
          <button class="ghost" id="gReplyImportBtn">导入</button>
          <input id="gReplyImport" type="file" accept=".json,application/json" style="display:none">
          <span id="gReplyMsg" class="hint"></span>
        </div>
      </section>

      <section>
        <h2>全局监听</h2>
        <p class="hint" style="margin-top:0">
          这里是所有群的默认值。某个群在「分群设置」里覆盖过的项以群设置为准，
          没有覆盖的项都跟随这里。QQ 群里还需要把「机器人可获取的群聊消息范围」
          设为「获取群内全部消息」，否则机器人只收得到 @ 消息。
        </p>
        <label class="chk"><input id="gLsOn" type="checkbox"> 允许在聊天模式监听群消息（总开关）</label>
        <div id="gListenFields" style="display:none">
        <div class="grid2" style="margin-top:10px">
          <div class="field">
            <label>默认接话概率（%）</label>
            <input id="gLsProb" type="number" min="0" max="100" step="5">
            <span class="hint">普通群消息按这个概率接话。0 表示只接关键词。</span>
          </div>
          <div class="field">
            <label>默认冷却（秒）</label>
            <input id="gLsCooldown" type="number" min="0" max="86400" step="10">
            <span class="hint">同一个群两次接话至少间隔这么久。</span>
          </div>
          <div class="field">
            <label>默认每天上限（条）</label>
            <input id="gLsDaily" type="number" min="0" max="10000" step="5">
            <span class="hint">0 表示不限。</span>
          </div>
          <div class="field">
            <label>默认最短字数</label>
            <input id="gLsMinChars" type="number" min="1" max="200" step="1">
            <span class="hint">太短的消息不接，避免“嗯”“哈哈”也触发。</span>
          </div>
          <div class="field">
            <label>默认群人数下限</label>
            <input id="gLsMinMembers" type="number" min="0" max="100000" step="5">
            <span class="hint">0 表示不限。低于这个人数的群不会接话。</span>
          </div>
        </div>
        <div class="field">
          <label>默认触发关键词（可选）</label>
          <textarea id="gLsKeywords" rows="3"
            placeholder="每行一个，或逗号分隔"></textarea>
          <span class="hint">命中关键词就跳过概率直接接话，仍然受冷却和每日上限限制。</span>
        </div>
        </div>
        <div class="row">
          <button id="gLsSave">保存全局监听</button>
          <span id="gLsMsg" class="hint"></span>
        </div>
      </section>

      <section>
        <h2>全局主动话题</h2>
        <label class="chk"><input id="gPrOn" type="checkbox"> 允许主动发起话题（总开关）</label>
        <p class="hint" style="margin-top:6px">
          总开关关闭时，所有群都不会主动发言；分群设置里的开关只决定本群是否启用。
          机器人会定时检查群，群安静后按概率主动开口；需要群允许「机器人主动发言」，
          发送失败不会退回被动回复。
        </p>
        <div id="gProactiveFields" style="margin-top:10px;display:none">
          <div class="grid2">
            <div class="field">
              <label>默认触发概率（%）</label>
              <input id="gPrProb" type="number" min="0" max="100" step="5">
              <span class="hint">每次后台检查，有多大概率主动开口。</span>
            </div>
            <div class="field">
              <label>默认冷却（秒）</label>
              <input id="gPrInterval" type="number" min="0" max="86400" step="30">
              <span class="hint">同一个群两次主动发言至少隔多久。0 表示不限制。</span>
            </div>
            <div class="field">
              <label>默认安静多久后（秒）</label>
              <input id="gPrIdle" type="number" min="0" max="86400" step="30">
              <span class="hint">群里至少安静这么久，机器人才会考虑主动开口。</span>
            </div>
            <div class="field">
              <label>默认每天上限（条）</label>
              <input id="gPrDaily" type="number" min="0" max="10000" step="1">
              <span class="hint">同一个群每天最多主动发言几次。0 表示不限制。</span>
            </div>
          </div>
          <div class="field">
            <label>默认主动话题提示词</label>
            <textarea id="gPrPrompt" rows="4"
              placeholder="根据最近的群聊，主动开一个轻松、适合群聊的话题。"></textarea>
          </div>
        </div>
        <div class="row">
          <button id="gPrSave">保存全局主动话题</button>
          <button class="ghost" id="prPromptExport">导出提示词</button>
          <button class="ghost" id="prPromptImportBtn">导入提示词</button>
          <input id="prPromptImport" type="file" accept=".json,application/json" style="display:none">
          <span id="gPrMsg" class="hint"></span>
        </div>
      </section>

      <section>
        <h2>运行参数（即时生效）</h2>
        <div id="settings"></div>
        <div class="row">
          <button id="stSave">保存参数</button>
          <button class="ghost" id="stReset">恢复默认</button>
          <span id="stMsg" class="hint"></span>
        </div>
      </section>

      <section>
        <h2>关键词规则</h2>
        <p class="hint" style="margin-top:0">
          消息命中正则就直接发固定回复，<strong>不调用模型、不消耗额度</strong>。
          从上往下匹配，第一条命中即止。
        </p>
        <div class="membar" style="margin-top:8px">
          <span class="hint">关键词规则文件</span>
          <div style="display:flex;align-items:center;gap:8px">
            <span id="ruleFileMsg" class="hint"></span>
            <button class="ghost mini" id="ruleExport">导出</button>
            <button class="ghost mini" id="ruleImportBtn">导入</button>
            <input id="ruleImport" type="file" accept=".json,application/json" style="display:none">
          </div>
        </div>
        <div id="rules" style="margin-top:12px"></div>
        <div class="row">
          <button class="ghost" id="ruleAdd">添加一条</button>
          <button id="ruleSave">保存规则</button>
          <span id="ruleMsg" class="hint"></span>
        </div>
        <p class="hint" style="margin-top:10px">
          这些规则只在你 @ 机器人时触发，命中后直接发固定回复、不调用模型。
          适合做口头禅、固定答疑、开场白这类不需要思考的内容。
        </p>
      </section>
    </div>

    <!-- ============ 分群回复设置 ============ -->
    <div class="panel" id="tab-reply">
      <div class="row" style="margin:0 0 6px">
        <label>当前群</label>
        <select id="rpGroup" class="mini-sel" style="min-width:240px"></select>
        <button class="ghost mini" id="rpGroupExport">导出设置</button>
        <button class="ghost mini" id="rpGroupImportBtn">导入设置</button>
        <input id="rpGroupImport" type="file" accept=".json,application/json" style="display:none">
        <button class="ghost mini" id="rpGroupReset">清除本群覆盖</button>
        <span id="rpGroupMsg" class="hint"></span>
      </div>
      <p class="hint" id="rpGroupScope" style="margin:0 0 8px"></p>
      <p class="hint" style="margin:0 0 10px">
        这里只保存本群覆盖。和全局默认相同的项会自动改为继承，之后全局改动会同步过来；
        想恢复继承，把值改回全局默认再保存。
      </p>

      <section>
        <h2>本群回复行为</h2>
        <div class="field">
          <label>本群兜底话术</label>
          <input id="rpFallback" maxlength="200"
            placeholder="模型超时或失败时发这句">
          <span class="hint">模型超时、报错、额度耗尽时使用。留空或与全局相同则继承。</span>
        </div>
        <div class="grid2" style="margin-top:12px">
          <div class="field">
            <label>本群单条字数上限</label>
            <input id="rpChunk" type="number" min="200" max="4000" step="100">
            <span class="hint">超过就拆分。QQ 单条消息太长阅读体验差。</span>
          </div>
          <div class="field">
            <label>本群最多分几条</label>
            <input id="rpChunks" type="number" min="1" max="5" step="1">
            <span class="hint">群被动回复每轮最多 5 次，默认 3 条留余量。</span>
          </div>
        </div>
        <div class="visionrow" style="margin-top:12px">
          <label class="chk"><input id="rpMulti" type="checkbox"> 本群分条发送消息</label>
          <span class="hint">按句号、问号、感叹号或空行拆成几条短消息，句号会被去掉，问号和感叹号保留。</span>
          <div class="grid2" style="margin-top:8px">
            <div class="field">
              <label>最多几条</label>
              <input id="rpMultiMax" type="number" min="1" max="5" step="1">
            </div>
            <div class="field">
              <label>每条间隔（毫秒）</label>
              <input id="rpMultiDelay" type="number" min="0" max="5000" step="100">
            </div>
          </div>
        </div>
        <label class="chk" style="margin-top:10px;white-space:normal">
          <input id="rpNoAt" type="checkbox">
          本群回复时不 @ 用户（改用主动消息，需要群开启「机器人主动发言」）
        </label>
        <div class="row">
          <button id="rpSave">保存本群回复</button>
          <span id="rpMsg" class="hint"></span>
        </div>
      </section>

      <section>
        <h2>本群监听</h2>
        <p class="hint" style="margin-top:0">
          还需要在 QQ 群里把「机器人可获取的群聊消息范围」设为「获取群内全部消息」，
          否则机器人只收得到 @ 消息。总开关在「全局回复设置」里。
        </p>
        <label class="chk"><input id="lsOn" type="checkbox"> 允许监听本群消息</label>
        <span id="lsMasterWarn" class="hint"
          style="display:none;color:#e6a23c;margin-top:6px"></span>
        <div id="listenFields" style="display:none">
        <div class="grid2" style="margin-top:10px">
          <div class="field">
            <label>接话概率（%）</label>
            <input id="lsProb" type="number" min="0" max="100" step="5">
            <span class="hint">每条普通消息按这个概率决定要不要接。0 表示只接关键词。</span>
          </div>
          <div class="field">
            <label>冷却（秒）</label>
            <input id="lsCooldown" type="number" min="0" max="86400" step="10">
            <span class="hint">同一个群两次接话至少间隔这么久。</span>
          </div>
          <div class="field">
            <label>每天上限（条）</label>
            <input id="lsDaily" type="number" min="0" max="10000" step="5">
            <span class="hint">0 表示不限。</span>
          </div>
          <div class="field">
            <label>最短字数</label>
            <input id="lsMinChars" type="number" min="1" max="200" step="1">
            <span class="hint">太短的消息不接，避免“嗯”“哈哈”也触发。</span>
          </div>
          <div class="field">
            <label>群人数下限</label>
            <input id="lsMinMembers" type="number" min="0" max="100000" step="5">
            <span class="hint">0 表示不限。群列表里人数未知或低于它的群不会接话。</span>
          </div>
        </div>
        <div class="field">
          <label>本群触发关键词（可选）</label>
          <textarea id="lsKeywords" rows="3"
            placeholder="每行一个，或逗号分隔"></textarea>
          <span class="hint">命中关键词就跳过概率直接接话，仍然受冷却和每日上限限制。</span>
        </div>
        </div>
        <div class="row">
          <button id="lsSave">保存本群监听</button>
          <span id="lsMsg" class="hint"></span>
        </div>
      </section>

      <section>
        <h2>本群主动话题</h2>
        <label class="chk"><input id="prActiveOn" type="checkbox"> 为本群启用主动发起话题</label>
        <span id="prMasterWarn" class="hint"
          style="display:none;color:#e6a23c;margin-top:6px"></span>
        <p class="hint" style="margin-top:6px">
          机器人会定时检查群，群安静后按概率主动开口。只在聊天模式生效；
          需要群允许「机器人主动发言」，发送失败不会退回被动回复。
        </p>
        <div id="proactiveFields" style="margin-top:10px;display:none">
          <div class="grid2">
            <div class="field">
              <label>触发概率（%）</label>
              <input id="prActiveProb" type="number" min="0" max="100" step="5">
              <span class="hint">每次后台检查，有多大概率主动开口。</span>
            </div>
            <div class="field">
              <label>冷却（秒）</label>
              <input id="prActiveInterval" type="number" min="0" max="86400" step="30">
              <span class="hint">同一个群两次主动发言至少隔多久。0 表示不限制。</span>
            </div>
            <div class="field">
              <label>安静多久后（秒）</label>
              <input id="prActiveIdle" type="number" min="0" max="86400" step="30">
              <span class="hint">群里至少安静这么久，机器人才会考虑主动开口。</span>
            </div>
            <div class="field">
              <label>每天上限（条）</label>
              <input id="prActiveDaily" type="number" min="0" max="10000" step="1">
              <span class="hint">同一个群每天最多主动发言几次。0 表示不限制。</span>
            </div>
          </div>
          <div class="field">
            <label>本群主动话题提示词</label>
            <textarea id="prActivePrompt" rows="4"
              placeholder="根据最近的群聊，主动开一个轻松、适合群聊的话题。"></textarea>
          </div>
        </div>
        <div class="row">
          <button id="prActiveSave">保存本群主动话题</button>
          <button class="ghost" id="prGroupPromptExport">导出提示词</button>
          <button class="ghost" id="prGroupPromptImportBtn">导入提示词</button>
          <input id="prGroupPromptImport" type="file" accept=".json,application/json" style="display:none">
          <span id="prActiveMsg" class="hint"></span>
        </div>
      </section>
    </div>
    <div class="panel" id="tab-groups">
      <section>
        <h2>今日额度</h2>
        <div class="kv" id="quotaKv"></div>
        <p class="hint" id="quotaDetail" style="margin:8px 0 0"></p>
        <div class="kv" id="quotaMuted" style="margin-top:6px"></div>
        <p class="hint" style="margin-top:10px">
          额度每天零点归零。到量后所有消息直接丢弃，不会回兜底话术。
        </p>
      </section>

      <section>
        <h2>机器人所在的群</h2>
        <p class="hint" style="margin-top:0">
          <strong>pending</strong> 是陌生人拉进来的群，还没批准，不会回复任何消息。
          <strong>active</strong> 才会工作。<strong>disabled</strong> 是手动停用。
        </p>
        <div id="groups" style="margin-top:12px">暂无</div>
      </section>

      <section>
        <h2>黑名单（被静默的人）</h2>
        <p class="hint" style="margin-top:0">
          被判定刷屏后自动加入，之后完全不回复。可随时解封。
        </p>
        <div id="mutedBox" style="margin-top:10px"></div>
      </section>
    </div>

    <!-- ============ 试聊 ============ -->
    <div class="panel" id="tab-chat">
      <div class="chatwrap">
        <div class="chatlog" id="chatLog"></div>
        <div class="chatinput">
          <input id="pvInput" placeholder="输入一句话，回车发送">
          <button id="pvSend">发送</button>
          <button class="ghost" id="pvReset">清空</button>
        </div>
      </div>
    </div>

    <!-- ============ 插件 ============ -->
    <div class="panel" id="tab-plugins">
      <section>
        <h2>内置插件</h2>
        <p class="hint">
          随程序发布、没有文件，只能整体启用或关闭。
        </p>
        <div id="builtinList" class="hint">加载中…</div>

        <div id="wikiConfig" style="margin-top:16px;border-top:1px solid #22262d;padding-top:14px">
          <label class="chk">
            <input type="checkbox" id="wikiTranslate">
            中文关键词没匹配上时，自动翻成英文再查一次（消耗少量模型额度）
          </label>
          <div class="field">
            <label>Wiki 站点（每行一个，名称|地址）</label>
            <textarea id="wikiSites" rows="5"
              placeholder="灰机wiki|https://www.huijiwiki.com"></textarea>
            <span class="hint">
              只支持 https 的 MediaWiki 站点（地址后面能加 <code>/api.php</code>），
              不要带路径、参数或开放的端口。外文站直接写域名即可，例如
              <code>Terraria|https://terraria.fandom.com</code>；
              中文关键词查不到时会自动翻成英文再搜。
            </span>
          </div>
          <div class="row">
            <button id="wikiSave">保存站点</button>
            <span id="wikiMsg" class="hint"></span>
          </div>
        </div>

        <div id="repeatConfig" style="margin-top:16px;border-top:1px solid #22262d;padding-top:14px">
          <div class="grid2">
            <div class="field">
              <label>触发概率（%）</label>
              <input id="rpRepeatProb" type="number" min="0" max="100" step="5">
              <span class="hint">
                每条符合条件的消息，有多大概率触发。100 一定触发，0 不触发。
              </span>
            </div>
            <div class="field">
              <label>冷却（秒）</label>
              <input id="rpRepeatCooldown" type="number" min="0" max="86400" step="10">
              <span class="hint">
                同一个群触发后，至少隔这么多秒才会再触发。0 表示不限制。
              </span>
            </div>
            <div class="field">
              <label>每天上限（条）</label>
              <input id="rpRepeatDaily" type="number" min="0" max="10000" step="5">
              <span class="hint">
                同一个群每天最多触发几次。0 表示不限制。
              </span>
            </div>
            <div class="field">
              <label>最长字数</label>
              <input id="rpRepeatMax" type="number" min="1" max="200" step="5">
              <span class="hint">
                超过这个字数的消息不处理，避免长文被复读或接梗。
              </span>
            </div>
            <div class="field">
              <label>方式</label>
              <select id="rpRepeatMode" class="mini-sel">
                <option value="both">复读和接梗</option>
                <option value="repeat">只允许复读</option>
                <option value="banter">只允许接梗</option>
              </select>
              <span class="hint">
                复读和接梗：允许机器人复读和接梗，每次触发随机选一种；只允许复读 / 只允许接梗：只用选中的那一种。
              </span>
            </div>
          </div>
          <span class="hint">
            复读和接梗只处理没 @ 机器人的消息，需要群里开启全量消息；只在聊天模式生效。
          </span>
          <div class="field">
            <label>接梗提示词</label>
            <textarea id="rpRepeatPrompt" rows="6"
              placeholder="[梗名]：对梗的解释，应该怎么接&#10;[急了]：调侃对方破防，应该回“这就急了？”&#10;[抽象]：故意说得离谱，应该接一句更离谱的"></textarea>
            <span class="hint">
              一行一个，格式为 <code>[梗名]：对梗的解释，应该怎么接</code>。
              只影响接梗，不影响复读和正经聊天；留空则只用通用接法。
            </span>
          </div>
          <div class="row">
            <button id="rpRepeatSave">保存设置</button>
            <button class="ghost" id="rpPromptExport">导出提示词</button>
            <button class="ghost" id="rpPromptImportBtn">导入提示词</button>
            <input id="rpPromptImport" type="file" accept=".json,application/json" style="display:none">
            <span id="rpRepeatMsg" class="hint"></span>
          </div>
        </div>

      </section>

      <section>
        <h2>模式</h2>
        <div id="modeList" class="hint">加载中…</div>
        <p class="hint" style="margin-top:10px">
          模式是群级设置，在「群聊与黑名单」里给每个群单独选；
          群里也可以由群主/管理员发 <code>/mode 模式id</code>。
          <b>trpg / minigame 不调用模型</b>，只响应指令。
          从界面切换时，如果 5 分钟内还有被动回复窗口会立即发说明，
          否则会在该群下一条消息里补发。
        </p>
      </section>

      <section>
        <h2>自定义模式</h2>
        <p class="hint">
          模式文件本地目录：<code>plugins\modes\</code>。
          只描述管线行为（是否调用模型、关键词是否生效、追加提示词），
          加载时不执行代码，导入后立即可用。
        </p>
        <p class="hint" style="color:#f1c40f">
          ⚠ 会调用模型的自定义模式（CALL_LLM = True）会单独保存一份对话历史和记忆，
          和普通聊天互不影响，来回切换不会串上下文。
          代价是每个模式各自消耗模型额度，记忆列表里也会按模式分开显示。
        </p>
        <div class="row">
          <button id="modeImport">导入模式 .py</button>
          <a class="mini ghost" id="modeTemplate"
             href="/api/modes/template" download="mode_template.py">下载模板</a>
          <button class="ghost" id="modeScan">重新扫描</button>
          <input type="file" id="modeFile" accept=".py" style="display:none">
          <span id="modeMsg" class="hint"></span>
        </div>
        <div id="modeErrors" class="hint" style="margin-top:8px"></div>
      </section>

      <section>
        <h2>代码插件</h2>
        <p class="hint">
          代码插件本地目录：<code>plugins\</code>（只扫描顶层的 <code>.py</code>）。
          <b>默认全部关闭</b>，需要在这里逐个启用。
        </p>
        <div id="codePlugins" class="hint">加载中…</div>
        <div class="row">
          <button class="ghost" id="codePluginScan">重新扫描</button>
          <span id="codePluginMsg" class="hint"></span>
        </div>
        <p class="hint" style="margin-top:10px">
          插件在独立子进程中运行：不能联网、不能写文件、不能启动其它程序，
          超过 3 秒会被强制结束。文件被修改后会自动停用，需要重新启用。
        </p>
        <div id="codePluginErrors" class="hint"></div>
      </section>

      <section>
        <h2>跑团规则</h2>
        <p class="hint">
          规则文件本地目录：<code>plugins\trpg\</code>。
          里面用 <code>FIELDS</code> / <code>CHECKS</code> 声明角色卡字段、公式和检定表。
          加载时只读取这些声明；只有声明了 <code>COMMANDS</code> 或
          <code>on_new</code> / <code>on_check</code> 的规则才会执行代码，
          并且在子进程沙箱里运行（禁网、禁写文件、3 秒超时）。
        </p>
        <div id="packList" class="hint">加载中…</div>
        <div class="row">
          <button id="packImport">导入规则 .py</button>
          <a class="mini ghost" id="packTemplate"
             href="/api/rulepacks/template" download="rule_template.py">下载模板</a>
          <button class="ghost" id="packReload">重新扫描</button>
          <input type="file" id="packFile" accept=".py" style="display:none">
          <span id="packMsg" class="hint"></span>
        </div>
        <p class="hint" style="margin-top:10px">
          每个群可以在「群聊与黑名单」里选择使用哪一套规则。
          含 <code>hook</code> 的规则默认关闭，需要点「启用 hook」才会执行；
          文件改动后会自动关闭。
        </p>
      </section>

      <section>
        <h2>小游戏</h2>
        <p class="hint">
          游戏文件本地目录：<code>plugins\minigame\</code>。
          游戏默认关闭，需要在这里启用；每个群可以单独选择在玩哪个游戏。
          游戏逻辑在子进程沙箱里运行，禁网、禁写文件、3 秒超时。
        </p>
        <div id="gameList" class="hint">加载中…</div>
        <div class="row">
          <button id="gameImport">导入游戏 .py</button>
          <a class="mini ghost" id="gameTemplate"
             href="/api/minigames/template" download="game_template.py">下载模板</a>
          <button class="ghost" id="gameScan">重新扫描</button>
          <input type="file" id="gameFile" accept=".py" style="display:none">
          <span id="gameMsg" class="hint"></span>
        </div>
        <p class="hint" style="margin-top:10px">
          启用后直接发对应指令即可，同一个群可以同时启用多款；
          单机游戏每人独立，群游戏全群共享。用 <code>/game</code> 查看列表。
        </p>
        <div id="gameErrors" class="hint"></div>
      </section>

      <section>
        <h2>加载错误</h2>
        <div id="packErrors" class="hint">无</div>
      </section>
    </div>

    <!-- ============ 帮助 ============ -->
    <div class="panel" id="tab-help">
      <div class="docwrap">
        <div class="docnav" id="helpNav"></div>
        <div class="doc" id="helpText">加载中…</div>
      </div>
    </div>
  </main>
</div>

<script>
const TOKEN = new URLSearchParams(location.search).get("t") || "";
const $ = (id) => document.getElementById(id);

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (e) {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return ok;
    } catch (err) {
      return false;
    }
  }
}

let PRESETS = [];
let PROV = {};
let ST = {};
let RULES = [];
let PERSONA_REPORTS = [];
let PERSONA_EDIT = -1;
let PERSONA_PAGE = 1;
let PERSONA_PAGES = 1;
let PERSONA_TOTAL = 0;
const PERSONA_PAGE_SIZE = 10;
let filled = { basic: false, global: false, persona: false, modes: false, plugins: false };
let GROUP_REPLY_LOADED = false;
let GROUP_REPLY_CURRENT = "";
let HELP = [];
let HELP_ID = "";
let HELP_VIEW = "help";
let HELP_LOADED = false;

/* ---------------- 基础 ---------------- */
async function api(path, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: { "Content-Type": "application/json", "X-Token": TOKEN, ...(opts.headers || {}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || body.detail || res.status);
  }
  return res.json();
}

function setDot(state) {
  const d = $("dot");
  d.className = "dot";
  if (state === "ready") d.classList.add("ready");
  else if (["connecting","identifying","resuming","reconnecting","idle"].includes(state)) d.classList.add("warn");
  else d.classList.add("err");
}

function fmtUptime(s) {
  const h = Math.floor(s/3600), m = Math.floor(s%3600/60), sec = s%60;
  return (h?h+"h ":"") + (m?m+"m ":"") + sec + "s";
}

/* ---------------- 侧栏 ---------------- */
document.querySelectorAll("aside .navmain button").forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll("aside .navmain button").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".asidefoot a").forEach(a => a.classList.remove("active"));
    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    $("tab-" + btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "persona") {
      loadMemoryPage(MEM_PAGE);
      loadReportsPage(PERSONA_PAGE);
    }
  };
});

document.querySelectorAll(".asidefoot a").forEach(a => {
  a.onclick = () => openHelp(a.dataset.doc);
});

async function openHelp(view) {
  HELP_VIEW = view === "changelog" ? "changelog" : "help";
  document.querySelectorAll("aside .navmain button").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".asidefoot a").forEach(x =>
    x.classList.toggle("active", x.dataset.doc === HELP_VIEW)
  );
  document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
  $("tab-help").classList.add("active");
  try {
    await ensureHelp();
    renderHelp();
  } catch (e) {
    $("helpText").innerHTML = `<p class="hint">加载失败：${esc(e.message)}</p>`;
  }
}

async function ensureHelp() {
  if (HELP_LOADED) return;
  const r = await api("/api/help");
  HELP = r.docs || [];
  HELP_ID = "";
  HELP_LOADED = true;
}

function helpDocs() {
  if (HELP_VIEW === "changelog") return HELP.filter(d => d.id === "changelog");
  return HELP.filter(d => d.id !== "changelog");
}

function renderHelp() {
  const docs = helpDocs();
  if (!docs.length) {
    $("helpNav").innerHTML = "";
    $("helpText").innerHTML = `<p class="hint">没有可显示的文档。</p>`;
    return;
  }
  if (!docs.some(d => d.id === HELP_ID)) HELP_ID = docs[0].id;
  $("helpNav").innerHTML = docs.length > 1
    ? docs.map(d => `<a data-help="${esc(d.id)}" class="${d.id === HELP_ID ? "active" : ""}">${esc(d.title)}</a>`).join("")
    : "";
  const doc = docs.find(d => d.id === HELP_ID) || docs[0];
  $("helpText").innerHTML = mdToHtml(doc.text);
}

$("helpNav").addEventListener("click", (e) => {
  const a = e.target.closest("a[data-help]");
  if (!a) return;
  HELP_ID = a.dataset.help;
  renderHelp();
  const main = document.querySelector("main");
  if (main) main.scrollTop = 0;
});

/* ---------------- 极简 Markdown 渲染（只用于帮助文档） ---------------- */
function mdInline(s) {
  let t = esc(s);
  t = t.replace(/`([^`]+)`/g, (m, c) => `<code>${c}</code>`);
  t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  t = t.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, label, href) => {
    const safe = /^https?:\/\//i.test(href) ? href : "#";
    return `<a href="${safe}" target="_blank" rel="noreferrer">${label}</a>`;
  });
  return t;
}

function mdToHtml(src) {
  const lines = String(src || "").replace(/\r\n?/g, "\n").split("\n");
  const out = [];
  let list = null;
  let i = 0;

  const flushList = () => {
    if (!list) return;
    const tag = list.type === "ol" ? "ol" : "ul";
    out.push(`<${tag}>` + list.items.map(x => `<li>${x}</li>`).join("") + `</${tag}>`);
    list = null;
  };
  const splitRow = (line) =>
    line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map(c => c.trim());
  const isAlignRow = (line) => /^\|?[\s:|-]*-[\s:|-]*\|?$/.test(line) && line.indexOf("-") >= 0;
  const blockStart = /^(#{1,6}\s|```|\||>\s?|\s*[-*]\s+|\s*\d+[.、]\s+)/;

  while (i < lines.length) {
    const line = lines[i];

    if (/^```/.test(line)) {
      flushList();
      const buf = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) { buf.push(lines[i]); i++; }
      i++;
      out.push(`<pre><code>${esc(buf.join("\n"))}</code></pre>`);
      continue;
    }

    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) {
      flushList();
      const lv = Math.min(h[1].length, 3);
      out.push(`<h${lv}>${mdInline(h[2])}</h${lv}>`);
      i++;
      continue;
    }

    if (/^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
      flushList();
      out.push("<hr>");
      i++;
      continue;
    }

    if (/^\|/.test(line) && i + 1 < lines.length && isAlignRow(lines[i + 1])) {
      flushList();
      const head = splitRow(line);
      i += 2;
      const rows = [];
      while (i < lines.length && /^\|/.test(lines[i])) { rows.push(splitRow(lines[i])); i++; }
      out.push(
        "<table><thead><tr>" +
        head.map(c => `<th>${mdInline(c)}</th>`).join("") +
        "</tr></thead><tbody>" +
        rows.map(r => "<tr>" + r.map(c => `<td>${mdInline(c)}</td>`).join("") + "</tr>").join("") +
        "</tbody></table>"
      );
      continue;
    }

    const ul = line.match(/^\s*[-*]\s+(.*)$/);
    const ol = line.match(/^\s*\d+[.、]\s+(.*)$/);
    if (ul || ol) {
      const type = ol ? "ol" : "ul";
      if (!list || list.type !== type) { flushList(); list = { type, items: [] }; }
      list.items.push(mdInline((ul || ol)[1]));
      i++;
      continue;
    }

    // 列表项后面的续行（缩进两格以上）
    if (list && /^\s{2,}\S/.test(line)) {
      const last = list.items.length - 1;
      list.items[last] = `${list.items[last]}<br>${mdInline(line.trim())}`;
      i++;
      continue;
    }

    if (/^>\s?/.test(line)) {
      flushList();
      const buf = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) {
        buf.push(lines[i].replace(/^>\s?/, ""));
        i++;
      }
      out.push(`<blockquote>${mdInline(buf.join(" "))}</blockquote>`);
      continue;
    }

    if (!line.trim()) { flushList(); i++; continue; }

    // txt 手册里的下划线式标题
    if (i + 1 < lines.length && /^={3,}\s*$/.test(lines[i + 1])) {
      flushList();
      out.push(`<h1>${mdInline(line)}</h1>`);
      i += 2;
      continue;
    }
    if (i + 1 < lines.length && /^-{3,}\s*$/.test(lines[i + 1])) {
      flushList();
      out.push(`<h2>${mdInline(line)}</h2>`);
      i += 2;
      continue;
    }

    flushList();
    const buf = [line];
    i++;
    while (
      i < lines.length &&
      lines[i].trim() &&
      !blockStart.test(lines[i]) &&
      !/^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(lines[i])
    ) {
      buf.push(lines[i]);
      i++;
    }
    out.push(`<p>${buf.map(mdInline).join("<br>")}</p>`);
  }
  flushList();
  return out.join("\n");
}

/* ---------------- 模型 ---------------- */
async function loadPresets() {
  try {
    const r = await api("/api/provider/presets");
    PRESETS = r.presets || [];
    const opts = PRESETS.map(p => `<option value="${p.id}">${p.label}</option>`).join("");
    $("pvKind").innerHTML = opts;
    if ($("pgKind")) {
      const real = PRESETS.filter(p => !["mock", "failing"].includes(p.id));
      $("pgKind").innerHTML =
        `<option value="">主模型（沿用当前）</option>` +
        real.map(p => `<option value="${p.id}">${p.label}</option>`).join("");
    }
  } catch (e) { /* 忽略 */ }
}

function setModelOptions(models, current) {
  const pick = $("pvModelPick");
  const list = (models || []).filter(Boolean);
  pick.innerHTML = `<option value="">${list.length ? "从列表选择…" : "还没有模型列表"}</option>` +
    list.map(m => `<option value="${esc(m)}">${esc(m)}</option>`).join("");
  pick.disabled = !list.length;
  pick.value = list.includes(current) ? current : "";
}

function applyPreset(id, force) {
  const p = PRESETS.find(x => x.id === id);
  if (!p) return;
  const isMock = p.id === "mock";
  const isCustom = p.id === "custom";

  $("pvBaseWrap").style.display = isCustom ? "" : "none";
  $("pvModelWrap").style.display = isMock ? "none" : "";
  $("pvKeyWrap").style.display = isMock ? "none" : "";

  const hasKey = (PROV.keyed || []).includes(p.id);
  if (force) $("pvKey").value = "";
  $("pvKey").placeholder = hasKey ? "该服务已保存，留空表示不修改" : "请填写 API Key";

  if (isCustom) { if (force) $("pvBase").value = ""; }
  else { $("pvBase").value = ""; }

  if (force) $("pvModel").value = isMock ? "" : ((p.models && p.models[0]) || "");
  setModelOptions(p.models || [], $("pvModel").value);

  $("pvNote").textContent = isMock
    ? "不使用真实 API，回复里会带上文轮数。"
    : (p.base_url ? `将使用 ${p.base_url}` : (p.note || ""));
}

/* ---------------- 运行参数 ---------------- */
const ALL_SETTINGS = [
  { k: "abuse_window_s", l: "统计窗口", u: "秒", h: "决定「警告阈值」和「静默阈值」按多长时间统计；窗口越短越敏感，60 秒是常用值。" },
  { k: "abuse_warn_threshold", l: "警告阈值", u: "次", h: "窗口内第几次 @ 触发警告。设为 6，就是第 7 次收到警告。" },
  { k: "abuse_warn_cooldown_s", l: "警告冷却", u: "秒", h: "警告后至少等这么久，才可能升级为静默。防止一次误判直接封人。" },
  { k: "abuse_mute_threshold", l: "静默阈值", u: "次", h: "冷却结束后仍在窗口内超限，超过这个次数就拉黑，之后完全不回。" },
  { k: "group_qpm", l: "单群每分钟", u: "条", h: "单个群的处理上限，超出直接丢弃。" },
  { k: "global_qpm", l: "全局每分钟", u: "条", h: "所有群合计上限，防止整体被打爆。" },
  { k: "daily_msg_budget", l: "每日消息额度", u: "条", h: "每天最多回复多少条，跨群累计。填 0 表示不限制。" },
  { k: "daily_token_budget", l: "每日 Token 额度", u: "", h: "每天最多消耗多少 token（含上下文）。填 0 表示不限制，这是控制花钱的主要开关。" },
  { k: "history_limit", l: "上下文条数", u: "条", h: "每次带给模型的历史消息条数。8–12 通常够用，越大越贵。" },
  { k: "max_tokens", l: "单次最大输出", u: "token", h: "模型单条回复的上限，超出会被截断。中文约 1 字 ≈ 1.5 token。" },
  { k: "audit_keep_days", l: "审计保留天数", u: "天", h: "超过这个天数的审计记录每小时自动清理一次。0 表示不按时间清理，只保留最近 5000 条。" },
];

function renderSettings() {
  $("settings").innerHTML = `<div class="fields2">` + ALL_SETTINGS.map(s =>
    `<div class="field">
       <label>${s.l}${s.u ? `（${s.u}）` : ""}</label>
       <input id="st_${s.k}" type="number" min="0">
       <span class="hint">${s.h}</span>
     </div>`).join("") + `</div>`;
}

/* ---------------- 刷新 ---------------- */
async function refresh() {
  try {
    const s = await api("/api/state");
    ST = s;
    setDot(s.state);
    $("stateText").textContent = s.state + (s.paused ? " · 已暂停" : "");
    $("inst").textContent = s.instance_id + "  v" + s.version;
    PROV = s.provider || {};
    $("auditInfo").textContent =
      `审计记录 ${s.audit_count ?? 0} 条，自动保留 ${(s.config && s.config.audit_keep_days) ?? 30} 天`;

    if (!filled.basic) {
      filled.basic = true;
      $("appId").value = s.app_id_full || "";
      $("appSecret").placeholder = s.has_secret ? "已保存，留空表示不修改" : "首次配置必填";
      $("pvKind").value = (s.provider && s.provider.id) || "mock";
      $("pvBase").value = (s.provider && s.provider.base_url) || "";
      $("pvModel").value = (s.provider && s.provider.model) || "";
      $("pvTimeout").value = (s.config && s.config.timeout_s) || 25;
      $("visionOn").checked = !!(s.config && s.config.vision_enabled);
      applyPreset((s.provider && s.provider.id) || "mock", false);
      ALL_SETTINGS.forEach(f => {
        const el = $("st_" + f.k);
        if (el) el.value = (s.config || {})[f.k] ?? "";
      });
      $("winCloseAction").value = (s.config && s.config.close_action) || "tray";
    }

    if (!filled.persona) {
      filled.persona = true;
      $("psName").value = s.persona.bot_name || "";
      $("psPersona").value = s.persona.persona || "";
      $("psNegative").value = s.persona.negative_prompt || "";
      $("psStyle").value = s.persona.style_prompt || "";
      $("memAuto").checked = !!(s.memory && s.memory.auto_summary);
      $("memTrigger").value = (s.memory && s.memory.trigger_tokens) || 8000;
      $("memTriggerMsgs").value = (s.memory && s.memory.trigger_messages) || 60;
    }

    if (s.memory) {
      const fixed = s.memory.fixed_tokens || 0;
      const hl = (s.config && s.config.history_limit) || 12;
      $("memCalc").textContent =
        `内置+固定提示词 ${fixed} token　·　按每个人、每种模式分别累计：` +
        `超出最近 ${hl} 条历史后，再攒到 ${s.memory.content_budget} token ` +
        `或 ${(s.memory.trigger_messages || 60)} 条整理一次；` +
        `每条记忆最多 10 条（6 条最新对话 + 4 条长期保留）`;
      const pend = s.memory.pending || {};
      $("memPending").textContent = pend.messages
        ? `待整理：${pend.people || 0} 人 / ${pend.threads || 0} 个对话 / 共 ${pend.messages} 条`
        : "待整理：暂无（还没有攒到需要整理的旧对话）";
    }

    if (!filled.global) {
      filled.global = true;
      $("gFallback").value = s.reply.fallback_reply || "";
      $("gChunk").value = s.reply.chunk_limit || 1200;
      $("gChunks").value = s.reply.max_chunks || 3;
      $("gMulti").checked = !!s.reply.multi_message;
      $("gMultiMax").value = s.reply.multi_message_max || 3;
      $("gMultiDelay").value = s.reply.multi_message_delay_ms ?? 700;
      $("gNoAt").checked = !!s.reply.reply_without_at;
      const lc = s.config || {};
      $("gLsOn").checked = !!lc.listen_enabled;
      $("gListenFields").style.display = $("gLsOn").checked ? "" : "none";
      $("gLsProb").value = lc.listen_probability ?? 15;
      $("gLsCooldown").value = lc.listen_cooldown_s ?? 120;
      $("gLsDaily").value = lc.listen_daily_limit ?? 30;
      $("gLsMinChars").value = lc.listen_min_chars ?? 4;
      $("gLsMinMembers").value = lc.listen_min_members ?? 0;
      $("gLsKeywords").value = (lc.listen_keywords || []).join("\n");
      $("gPrOn").checked = !!lc.proactive_enabled;
      $("gProactiveFields").style.display = $("gPrOn").checked ? "" : "none";
      $("gPrProb").value = lc.proactive_probability ?? 10;
      $("gPrInterval").value = lc.proactive_interval_s ?? 600;
      $("gPrIdle").value = lc.proactive_idle_s ?? 300;
      $("gPrDaily").value = lc.proactive_daily_limit ?? 5;
      $("gPrPrompt").value = lc.proactive_prompt || "";
      $("rpRepeatProb").value = lc.repeat_probability ?? 10;
      $("rpRepeatCooldown").value = lc.repeat_cooldown_s ?? 60;
      $("rpRepeatDaily").value = lc.repeat_daily_limit ?? 20;
      $("rpRepeatMax").value = lc.repeat_max_chars ?? 40;
      $("rpRepeatMode").value = lc.repeat_mode || "both";
      $("rpRepeatPrompt").value = lc.repeat_prompt || "";
      $("pgOn").checked = !!lc.persona_guard_enabled;
      $("personaFields").style.display = $("pgOn").checked ? "" : "none";
      $("pgAnchor").value = lc.persona_anchor || "";
      $("pgCheck").value = lc.persona_check_interval ?? 20;
      $("pgUseModel").checked = !!lc.persona_check_use_separate;
      $("pgKind").value = lc.persona_check_provider || "";
      if (!Array.from($("pgKind").options).some(o => o.value === $("pgKind").value)) {
        $("pgKind").value = "";
      }
      $("pgBase").value = lc.persona_check_base_url || "";
      $("pgModel").value = lc.persona_check_model || "";
      $("pgKey").value = "";
      $("pgKeyHint").textContent = s.has_persona_check_key
        ? "已保存，留空表示不修改"
        : "未单独保存，留空沿用主模型 Key";
      $("pgModelBox").style.display = $("pgUseModel").checked ? "" : "none";
      if (typeof applyPgPreset === "function") applyPgPreset(false);
      RULES = (s.keyword_rules || []).map(r => ({
        pattern: r.pattern || "", reply: r.reply || "", enabled: r.enabled !== false,
      }));
      renderRules();
    }
    updateListenMasterHint($("lsOn").checked);
    updateProactiveMasterHint($("prActiveOn").checked);

    if (!filled.plugins) {
      filled.plugins = true;
      renderBuiltins(s);
      renderPacks(s);
      renderCodePlugins(s);
      renderGames(s);
      renderModes(s);
      $("wikiTranslate").checked = !s.config || s.config.wiki_translate !== false;
      $("wikiSites").value = ((s.config && s.config.wiki_sites) || []).join("\n");
    }

    $("pause").textContent = s.paused ? "恢复接收" : "暂停接收";

    const q = s.quota || {};
    const fmtQ = (used, limit) => `${used || 0} / ${limit > 0 ? limit : "不限"}`;
    $("quotaKv").innerHTML = [
      ["日期", q.date || "-"],
      ["消息数", fmtQ(q.msgs, q.msg_limit)],
      ["Token 总计", fmtQ(q.tokens, q.token_limit)],
    ].map(([k, v]) => `<div>${k}</div><div>${v}</div>`).join("");
    $("quotaDetail").textContent =
      `输入 ${q.prompt_tokens || 0} · 输出 ${q.completion_tokens || 0} · 缓存命中 ${q.cached_tokens || 0}`;
    $("quotaMuted").innerHTML =
      `<div>静默人数</div><div>${(s.muted || []).length}</div>`;

    const muted = s.muted || [];
    $("mutedBox").innerHTML = muted.length
      ? muted.map(u => `<div class="grow">
           <code style="color:#8b93a1">…${esc(String(u.group).slice(-6))} / …${esc(String(u.member).slice(-6))}</code>
           <span class="tag muted">静默</span>
           <span class="hint">${esc(u.reason || "")}</span>
           <span style="flex:1"></span>
           <button class="mini" data-unmute-g="${esc(u.group)}" data-unmute-m="${esc(u.member)}">解封</button>
         </div>`).join("")
      : `<span class="hint">暂无被静默的成员</span>`;

    renderGroups(s.groups || [], (s.packs || []).filter(p => p.enabled), s.modes || []);
    renderReplyGroups(s.groups || []);
  } catch (e) {
    $("stateText").textContent = "界面异常：" + e.message;
  }
}

function renderGroups(groups, packs = [], modes = []) {
  const box = $("groups");
  if (!groups.length) { box.innerHTML = `<span class="hint">暂无群</span>`; return; }
  const rules = [["default", "默认房规"], ["hr2", "房规二"], ["hr3", "房规三"], ["hr4", "房规四"]];
  const packOpts = (sel) => [`<option value="" ${!sel ? "selected" : ""}>自动</option>`].concat(
    packs.map(p => `<option value="${esc(p.id)}" ${sel === p.id ? "selected" : ""}>${esc(p.name)}</option>`)
  ).join("");
  box.innerHTML = groups.map(g => `
    <div class="grow">
      <code style="color:#8b93a1;user-select:all;word-break:break-all">${esc(g.group)}</code>
      <button class="mini ghost" data-copy="${esc(g.group)}">复制</button>
      <span class="tag ${esc(g.status)}">${esc(g.status)}</span>
      <select class="mini-sel" data-gp="${esc(g.group)}" title="跑团规则">
        ${packOpts(g.rulepack || "")}
      </select>
      <select class="mini-sel" data-gr="${esc(g.group)}" title="房规">
        ${rules.map(([v, l]) => `<option value="${v}" ${(g.house_rule || "default") === v ? "selected" : ""}>${l}</option>`).join("")}
      </select>
      <select class="mini-sel" data-gm="${esc(g.group)}" title="模式">
        ${(modes.length ? modes : [{ id: "chat", label: "聊天" }]).map(m =>
          `<option value="${esc(m.id)}" ${(g.mode || "chat") === m.id ? "selected" : ""}>${esc(m.label)}</option>`
        ).join("")}
      </select>
      <button class="mini ${g.listen_enabled ? "" : "ghost"}" data-gl="${esc(g.group)}"
              data-on="${g.listen_enabled ? "0" : "1"}">${g.listen_enabled ? "监听中" : "监听"}</button>
      <input class="mini-sel" type="number" min="0" max="100000" step="5"
             data-gn="${esc(g.group)}" value="${g.member_count || 0}"
             title="群人数（用于监听的人数下限）" style="width:76px">
      <span style="flex:1"></span>
      ${g.status !== "active" ? `<button class="mini" data-g="${esc(g.group)}" data-s="active">批准</button>` : ""}
      ${g.status !== "disabled" ? `<button class="mini ghost" data-g="${esc(g.group)}" data-s="disabled">停用</button>` : ""}
    </div>`).join("");
}

function renderPacks(s) {
  const packs = s.packs || [];
  $("packList").innerHTML = packs.length
    ? packs.map(p => `<div class="grow">
         <strong>${esc(p.name)}</strong>
         <code style="color:#8b93a1">${esc(p.id)}${p.source === "py" ? ".py" : "/"}</code>
         <span class="tag ${p.enabled ? "active" : "disabled"}">${p.enabled ? "已启用" : "已关闭"}</span>
         <span class="hint">${p.fields} 个字段 · ${p.checks || 0} 套检定 · ${p.house_rules || 0} 套房规</span>
         ${p.enabled && p.hooks && p.hooks.length ? `<button class="mini ${p.hooks_active ? "ghost" : ""}" data-hook="${esc(p.id)}" data-on="${p.hooks_active ? "0" : "1"}">${p.hooks_active ? "关闭 hook" : "启用 hook"}</button>` : ""}
         <span style="flex:1"></span>
         <button class="mini ${p.enabled ? "ghost" : ""}" data-pack="${esc(p.id)}"
                 data-on="${p.enabled ? "0" : "1"}">${p.enabled ? "关闭" : "启用"}</button>
         ${p.source === "py" ? `<a class="mini ghost"
            href="/api/rulepacks/${encodeURIComponent(p.id)}/export?t=${encodeURIComponent(TOKEN)}"
            download="${esc(p.id)}.py">导出</a>` : ""}
       </div>`).join("")
    : `<span class="hint">还没有规则插件</span>`;

  const errs = s.pack_errors || [];
  $("packErrors").innerHTML = errs.length
    ? errs.map(e => `<div class="bad" style="padding:4px 0">${esc(e)}</div>`).join("")
    : `<span class="hint">无</span>`;
}

function renderCodePlugins(data) {
  const list = data.code_plugins || data.plugins || [];
  const errs = data.code_plugin_errors || data.errors || [];
  const box = $("codePlugins");

  if (!list.length) {
    box.innerHTML = `<span class="hint">plugins/ 下还没有 .py 文件</span>`;
  } else {
    box.innerHTML = list.map(p => {
      const badge = p.error
        ? `<span class="tag removed">有问题</span>`
        : (p.enabled ? `<span class="tag active">已启用</span>` : `<span class="tag disabled">已关闭</span>`);
      const cmds = (p.commands || []).map(c => "/" + c).join(" ");
      return `<div class="grow">
        <strong>${esc(p.name)}</strong>
        <code style="color:#8b93a1">${esc(p.id)}.py</code>
        ${badge}
        <span class="hint">${esc(cmds) || "无指令"}</span>
        ${p.description ? `<span class="hint">${esc(p.description)}</span>` : ""}
        ${p.error ? `<span class="bad">${esc(p.error)}</span>` : ""}
        <span style="flex:1"></span>
        <button class="mini ${p.enabled ? "ghost" : ""}" data-plug="${esc(p.id)}"
                data-on="${p.enabled ? "0" : "1"}" ${p.error ? "disabled" : ""}>
          ${p.enabled ? "关闭" : "启用"}
        </button>
      </div>`;
    }).join("");
  }

  $("codePluginErrors").innerHTML = errs.length
    ? errs.map(e => `<div class="bad" style="padding:4px 0">${esc(e)}</div>`).join("")
    : "";
}

function renderModes(data) {
  const list = data.modes || [];
  const errs = data.mode_errors || data.errors || [];
  $("modeList").innerHTML = list.map(m => `<div class="grow">
    <code style="color:#8b93a1">${esc(m.id)}</code>
    <strong>${esc(m.label)}</strong>
    <span class="tag ${m.call_llm ? "active" : "disabled"}">${m.call_llm ? "调用模型" : "不调用模型"}</span>
    ${m.allow_keyword ? `<span class="tag mode">关键词生效</span>` : ""}
    ${m.source !== "builtin" && m.call_llm ? `<span class="tag active" title="独立保存对话历史与记忆，与聊天模式互不影响">独立上下文</span>` : ""}
    <span class="tag ${m.source === "builtin" ? "disabled" : "pending"}">${m.source === "builtin" ? "内置" : "自定义"}</span>
    ${m.description ? `<span class="hint">${esc(m.description)}</span>` : ""}
    <span style="flex:1"></span>
    ${m.source === "builtin" ? "" : `<a class="mini ghost"
       href="/api/modes/${encodeURIComponent(m.id)}/export?t=${encodeURIComponent(TOKEN)}"
       download="${esc(m.id)}.py">导出</a>`}
  </div>`).join("");

  $("modeErrors").innerHTML = errs.length
    ? errs.map(e => `<div class="bad" style="padding:4px 0">${esc(e)}</div>`).join("")
    : "";
}

function renderBuiltins(data) {
  const list = data.builtins || [];
  $("builtinList").innerHTML = list.length
    ? list.map(b => `
      <div class="grow">
        <strong>${esc(b.name)}</strong>
        <span class="tag ${b.enabled ? "active" : "disabled"}">${b.enabled ? "已启用" : "已关闭"}</span>
        <span class="hint">${esc((b.commands || []).join("　"))}</span>
        <span style="flex:1"></span>
        <button class="mini ${b.enabled ? "ghost" : ""}" data-builtin="${esc(b.id)}"
                data-on="${b.enabled ? "0" : "1"}">${b.enabled ? "关闭" : "启用"}</button>
      </div>
      <div class="hint" style="margin:0 0 10px">${esc(b.description)}${b.enabled ? "" : "　启用后才能查看和修改它的具体设置。"}</div>
    `).join("")
    : `<span class="hint">没有内置插件</span>`;
  $("wikiConfig").style.display = list.some(b => b.id === "wiki" && b.enabled) ? "" : "none";
  $("repeatConfig").style.display =
    list.some(b => b.id === "repeat" && b.enabled) ? "" : "none";
}

$("builtinList").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-builtin]");
  if (!btn) return;
  const enable = btn.dataset.on === "1";
  btn.disabled = true;
  try {
    await api(`/api/builtins/${encodeURIComponent(btn.dataset.builtin)}/enable`, {
      method: "POST", body: JSON.stringify({ enabled: enable }),
    });
    filled.plugins = false;
    await refresh();
  } catch (err) {
    btn.disabled = false;
    alert("操作失败：" + err.message);
  }
});

function renderGames(data) {
  const list = data.games || [];
  const errs = data.game_errors || data.errors || [];
  const box = $("gameList");

  if (!list.length) {
    box.innerHTML = `<span class="hint">plugins/minigame/ 下还没有 .py 文件</span>`;
  } else {
    box.innerHTML = list.map(g => {
      const cmds = (g.commands || []).map(c => "/" + c).join(" ");
      const mode = g.mode === "daily" ? "每天一次" : "按局";
      const scope = g.scope === "group" ? "全群" : "单人";
      return `<div class="grow">
        <strong>${esc(g.name)}</strong>
        <code style="color:#8b93a1">${esc(g.id)}.py</code>
        <span class="hint">${mode} · ${scope}</span>
        <span class="tag ${g.enabled ? "active" : "disabled"}">${g.enabled ? "已启用" : "已关闭"}</span>
        <span class="hint">${esc(cmds) || "无指令"}</span>
        ${g.error ? `<span class="bad">${esc(g.error)}</span>` : ""}
        <span style="flex:1"></span>
        ${g.error ? "" : `<button class="mini ${g.enabled ? "ghost" : ""}" data-game="${esc(g.id)}"
                data-on="${g.enabled ? "0" : "1"}">${g.enabled ? "关闭" : "启用"}</button>`}
        <a class="mini ghost"
           href="/api/minigames/${encodeURIComponent(g.id)}/export?t=${encodeURIComponent(TOKEN)}"
           download="${esc(g.id)}.py">导出</a>
      </div>`;
    }).join("");
  }

  $("gameErrors").innerHTML = errs.length
    ? errs.map(e => `<div class="bad" style="padding:4px 0">${esc(e)}</div>`).join("")
    : "";
}

let CHAT = [];

function renderChat() {
  $("chatLog").innerHTML = CHAT.map(m => {
    if (m.role === "sys") return `<div class="msg sys">${esc(m.text)}</div>`;
    const side = m.role === "user" ? "user" : "bot";
    const who = m.role === "user" ? "User" : "Bot";
    return `<div class="line ${side}">
      <div class="who">${who}</div>
      <div class="msg ${side}">${esc(m.text)}</div>
    </div>`;
  }).join("");
  $("chatLog").scrollTop = $("chatLog").scrollHeight;
}

async function doPreview() {
  const text = $("pvInput").value.trim();
  if (!text) return;
  CHAT.push({ role: "user", text });
  $("pvInput").value = "";
  renderChat();

  $("pvSend").disabled = true;
  try {
    const r = await api("/api/chat/preview", { method: "POST", body: JSON.stringify({ text }) });
    if (r.error) CHAT.push({ role: "sys", text: "⚠ " + r.error });
    CHAT.push({ role: "bot", text: r.reply });
    if ((r.chunks || []).length > 1) {
      CHAT.push({ role: "sys", text: `会分 ${r.chunks.length} 条发送` });
    }
  } catch (e) {
    CHAT.push({ role: "sys", text: "发送失败：" + e.message });
  } finally {
    renderChat();
    $("pvSend").disabled = false;
    $("pvInput").focus();
  }
}

$("saveCred").onclick = async () => {
  const app_id = $("appId").value.trim();
  const app_secret = $("appSecret").value.trim();
  if (!app_id) return alert("请填写 AppID");
  $("saveCred").disabled = true;
  try {
    await api("/api/config", { method: "POST", body: JSON.stringify({ app_id, app_secret }) });
    $("appSecret").value = "";
    await refresh();
  } catch (e) { alert("保存失败：" + e.message); }
  finally { $("saveCred").disabled = false; }
};

$("disconnect").onclick = async () => { await api("/api/disconnect", { method: "POST" }); refresh(); };
$("pause").onclick = async () => {
  try {
    await api("/api/pause", { method: "POST", body: JSON.stringify({ paused: !ST.paused }) });
    refresh();
  } catch (e) { alert("操作失败：" + e.message); }
};

$("pvKind").addEventListener("change", () => applyPreset($("pvKind").value, true));

$("pvModelPick").addEventListener("change", () => {
  const v = $("pvModelPick").value;
  if (!v) return;
  $("pvModel").value = v;
  $("pvStatus").textContent = "已选择 " + v;
});

$("pvFetchModels").onclick = async () => {
  $("pvFetchModels").disabled = true;
  $("pvStatus").textContent = "读取模型列表…";
  try {
    const r = await api("/api/provider/models", { method: "POST", body: JSON.stringify({
      base_url: $("pvKind").value === "custom" ? $("pvBase").value.trim() : "",
      api_key: $("pvKey").value.trim(),
    })});
    const models = (r.models || []).filter(Boolean);
    if (!$("pvModel").value && models.length) $("pvModel").value = models[0];
    setModelOptions(models, $("pvModel").value);
    $("pvStatus").textContent = `读取到 ${r.count} 个模型，可在左侧下拉里选择`;
  } catch (e) { $("pvStatus").textContent = "读取失败：" + e.message; }
  finally { $("pvFetchModels").disabled = false; }
};

$("pvSave").onclick = async () => {
  $("pvSave").disabled = true;
  $("pvStatus").textContent = "保存中…";
  try {
    const r = await api("/api/provider", { method: "POST", body: JSON.stringify({
      provider: $("pvKind").value,
      base_url: $("pvKind").value === "custom" ? $("pvBase").value.trim() : "",
      model: $("pvModel").value.trim(),
      api_key: $("pvKey").value.trim(),
      timeout_s: Number($("pvTimeout").value) || 25,
    })});
    $("pvKey").value = "";
    await api("/api/settings", { method: "POST", body: JSON.stringify({
      vision_enabled: $("visionOn").checked,
    })});
    $("pvStatus").textContent = r.ready ? "已生效" : "已保存，但未就绪（看运行状态里的错误）";
    filled.basic = false;
    await refresh();
  } catch (e) { $("pvStatus").textContent = "保存失败：" + e.message; }
  finally { $("pvSave").disabled = false; }
};

$("pvTest").onclick = async () => {
  $("pvTest").disabled = true;
  $("pvStatus").textContent = "测试中…";
  try {
    const r = await api("/api/provider/test", { method: "POST" });
    $("pvStatus").textContent = (r.ok ? "✓ " : "✗ ") + r.detail + ` （${r.latency_ms}ms）`;
  } catch (e) { $("pvStatus").textContent = "测试失败：" + e.message; }
  finally { $("pvTest").disabled = false; }
};

$("visionTest").onclick = async () => {
  $("visionTest").disabled = true;
  $("pvStatus").textContent = "正在测试看图…";
  try {
    const r = await api("/api/provider/test_vision", { method: "POST" });
    const ms = r.latency_ms ? `（${r.latency_ms}ms）` : "";
    $("pvStatus").textContent = r.ok
      ? `看图：${r.detail}${ms}　它应该说「红色」`
      : `看图失败${ms}：${r.detail}`;
  } catch (e) { $("pvStatus").textContent = "看图测试失败：" + e.message; }
  finally { $("visionTest").disabled = false; }
};

$("wikiSave").onclick = async () => {
  const sites = $("wikiSites").value
    .split("\n").map(x => x.trim()).filter(Boolean);
  $("wikiSave").disabled = true;
  $("wikiMsg").textContent = "保存中…";
  try {
    await api("/api/settings", { method: "POST", body: JSON.stringify({
      wiki_translate: $("wikiTranslate").checked,
      wiki_sites: sites,
    })});
    $("wikiMsg").textContent = `已保存（${sites.length} 个站点）`;
    filled.plugins = false;
    await refresh();
  } catch (e) { $("wikiMsg").textContent = "保存失败：" + e.message; }
  finally { $("wikiSave").disabled = false; }
};

$("stSave").onclick = async () => {
  const body = {};
  ALL_SETTINGS.forEach(f => {
    const el = $("st_" + f.k);
    if (el && el.value !== "") body[f.k] = Number(el.value);
  });
  $("stSave").disabled = true;
  $("stMsg").textContent = "保存中…";
  try {
    const r = await api("/api/settings", { method: "POST", body: JSON.stringify(body) });
    const n = Object.keys(r.changed || {}).length;
    $("stMsg").textContent = n ? `已更新 ${n} 项` : "没有变化";
    filled.basic = false;
    await refresh();
  } catch (e) { $("stMsg").textContent = "保存失败：" + e.message; }
  finally { $("stSave").disabled = false; }
};

$("stReset").onclick = async () => {
  try {
    const r = await api("/api/settings/defaults");
    ALL_SETTINGS.forEach(f => {
      const el = $("st_" + f.k);
      if (el) el.value = r.defaults[f.k] ?? "";
    });
    $("stMsg").textContent = "已填入默认值，点「保存参数」生效";
  } catch (e) { $("stMsg").textContent = "读取默认值失败：" + e.message; }
};

$("winSave").onclick = async () => {
  const action = $("winCloseAction").value;
  $("winSave").disabled = true;
  $("winMsg").textContent = "保存中…";
  try {
    await api("/api/settings", { method: "POST", body: JSON.stringify({ close_action: action }) });
    $("winMsg").textContent = action === "exit" ? "已保存：点 X 退出程序" : "已保存：点 X 缩到托盘";
    filled.basic = false;
    await refresh();
  } catch (e) { $("winMsg").textContent = "保存失败：" + e.message; }
  finally { $("winSave").disabled = false; }
};

let MEM = [];
let MEM_EDIT = -1;
let MEM_PAGE = 1;
let MEM_PAGES = 1;
let MEM_TOTAL = 0;
const MEM_PAGE_SIZE = 10;

function renderPager(id, page, pages, kind) {
  const el = $(id);
  if (!el) return;
  if (pages <= 1) {
    el.innerHTML = "";
    return;
  }
  el.innerHTML =
    `<button class="ghost mini" data-pager="${kind}" data-dir="-1" ${page <= 1 ? "disabled" : ""}>上一页</button>` +
    `<span class="hint">第 ${page} / ${pages} 页</span>` +
    `<button class="ghost mini" data-pager="${kind}" data-dir="1" ${page >= pages ? "disabled" : ""}>下一页</button>`;
}

function renderMemory() {
  if (MEM_EDIT >= MEM.length) MEM_EDIT = -1;
  if (!MEM.length) {
    $("memList").innerHTML =
      `<span class="hint">还没有生成任何记忆。开启自动总结并积累对话后会自动出现。</span>`;
    renderPager("memPager", 1, 1, "mem");
    return;
  }

  const rows = MEM.map((it, i) => {
    const summary = String(it.summary || "").trim();
    const display = summary
      ? (summary.startsWith("-") ? summary : "- " + summary)
      : "- （无记忆内容）";
    const head = `<div class="memrow2">
        <code style="color:#8b93a1">…${it.group.slice(-6)} / …${it.member.slice(-6)}</code>
        <span class="tag mode">${esc(it.mode || "chat")}</span>
      </div>`;
    if (i === MEM_EDIT) {
      return `<div class="memitem">
        ${head}
        <div class="memtextrow">
          <textarea data-editbox="${i}" rows="4" style="flex:1;min-width:0">${esc(it.summary)}</textarea>
          <div class="memactions">
            <button class="mini" data-save="${i}">保存</button>
            <button class="mini ghost" data-cancel="${i}">取消</button>
          </div>
        </div>
      </div>`;
    }
    return `<div class="memitem">
      ${head}
      <div class="memtextrow">
        <div class="memtext">${esc(display)}</div>
        <div class="memactions">
          <button class="mini ghost" data-edit="${i}">编辑</button>
          <button class="mini ghost" data-remove="${i}">删除</button>
        </div>
      </div>
    </div>`;
  }).join("");
  $("memList").innerHTML = `<div class="memlist">${rows}</div>`;
  renderPager("memPager", MEM_PAGE, MEM_PAGES, "mem");
}

async function loadMemoryPage(page) {
  if (MEM_EDIT >= 0) return;
  try {
    const r = await api(`/api/memory/page?page=${page}&size=${MEM_PAGE_SIZE}`);
    MEM = r.items || [];
    MEM_PAGE = r.page || 1;
    MEM_PAGES = r.pages || 1;
    MEM_TOTAL = r.total || 0;
    renderMemory();
  } catch (e) { /* 保持当前页 */ }
}

$("memList").addEventListener("click", async (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  const d = b.dataset;

  if (d.edit !== undefined) { MEM_EDIT = Number(d.edit); renderMemory(); return; }
  if (d.cancel !== undefined) { MEM_EDIT = -1; renderMemory(); return; }

  if (d.save !== undefined) {
    const i = Number(d.save);
    const box = document.querySelector(`[data-editbox="${i}"]`);
    const text = box ? box.value.trim() : "";
    if (!text) return alert("内容不能为空");
    try {
      await api("/api/memory/item", { method: "POST", body: JSON.stringify({
        group: MEM[i].group, member: MEM[i].member, mode: MEM[i].mode || "chat", summary: text,
      })});
      MEM_EDIT = -1;
      await loadMemoryPage(MEM_PAGE);
    } catch (err) { alert("保存失败：" + err.message); }
    return;
  }

  if (d.remove !== undefined) {
    const i = Number(d.remove);
    if (!confirm(`删除这条记忆？该用户在「${MEM[i].mode || "chat"}」模式下的历史记忆会被清空。`)) return;
    try {
      await api("/api/memory/item/delete", { method: "POST", body: JSON.stringify({
        group: MEM[i].group, member: MEM[i].member, mode: MEM[i].mode || "chat",
      })});
      MEM_EDIT = -1;
      await loadMemoryPage(MEM_PAGE);
    } catch (err) { alert("删除失败：" + err.message); }
  }
});

$("memPager").addEventListener("click", async (e) => {
  const b = e.target.closest("[data-pager]");
  if (!b || MEM_EDIT >= 0) return;
  MEM_PAGE += Number(b.dataset.dir) || 0;
  await loadMemoryPage(MEM_PAGE);
});

$("memSave").onclick = async () => {
  $("memSave").disabled = true;
  $("memMsg").textContent = "保存中…";
  try {
    await api("/api/memory", { method: "POST", body: JSON.stringify({
      auto_summary: $("memAuto").checked,
      trigger_tokens: Number($("memTrigger").value) || 8000,
      trigger_messages: Number($("memTriggerMsgs").value) || 60,
    })});
    $("memMsg").textContent = "已保存";
    filled.persona = false;
    await refresh();
  } catch (e) { $("memMsg").textContent = "保存失败：" + e.message; }
  finally { $("memSave").disabled = false; }
};

$("memExport").onclick = async () => {
  try {
    const r = await api("/api/memory/export");
    $("memFileMsg").textContent = "已导出到 " + r.path;
  } catch (e) { $("memFileMsg").textContent = "导出失败：" + e.message; }
};

$("memSummarize").onclick = async () => {
  $("memSummarize").disabled = true;
  $("memSumMsg").textContent = "整理中…（思考型模型可能需要 1～2 分钟）";
  try {
    const r = await api("/api/memory/summarize", {
      method: "POST", body: JSON.stringify({ limit: 3 }),
    });
    const left = (r.pending && r.pending.threads) || 0;
    $("memSumMsg").textContent = r.summarized
      ? `已整理 ${r.summarized} 个对话` + (left ? `，还有 ${left} 个对话待整理` : "")
      : (r.failed ? "整理失败，待处理内容已保留" : "没有可整理的对话");
    await refresh();
    await loadMemoryPage(MEM_PAGE);
  } catch (e) {
    $("memSumMsg").textContent = "整理失败：" + e.message;
  } finally {
    $("memSummarize").disabled = false;
  }
};

$("memImportBtn").onclick = () => $("memImport").click();

$("memImport").addEventListener("change", async (e) => {
  const f = e.target.files && e.target.files[0];
  e.target.value = "";
  if (!f) return;
  try {
    const payload = JSON.parse(await f.text());
    const r = await api("/api/memory/import", { method: "POST", body: JSON.stringify({ data: payload }) });
    filled.persona = false;
    MEM_PAGE = 1;
    await refresh();
    await loadMemoryPage(1);
    $("memFileMsg").textContent = `已导入，恢复 ${r.restored || 0} 条记忆`;
  } catch (err) { $("memFileMsg").textContent = "导入失败：" + err.message; }
});

$("psSave").onclick = async () => {
  $("psSave").disabled = true;
  $("psMsg").textContent = "保存中…";
  try {
    const r = await api("/api/persona", { method: "POST", body: JSON.stringify({
      bot_name: $("psName").value,
      persona: $("psPersona").value,
      negative_prompt: $("psNegative").value,
      style_prompt: $("psStyle").value,
    })});
    $("psMsg").textContent = "已保存（名字：" + (r.bot_name || "未设置") + "）";
  } catch (e) { $("psMsg").textContent = "保存失败：" + e.message; }
  finally { $("psSave").disabled = false; }
};

function cfgVal(key) {
  return (ST.config || {})[key];
}

function sameVal(a, b) {
  if (Array.isArray(a) || Array.isArray(b)) {
    const aa = Array.isArray(a) ? a : [];
    const bb = Array.isArray(b) ? b : [];
    return aa.length === bb.length &&
      aa.every((v, i) => String(v).trim() === String(bb[i]).trim());
  }
  if (typeof a === "boolean" || typeof b === "boolean") return !!a === !!b;
  if (typeof a === "number" || typeof b === "number") {
    return Number(a || 0) === Number(b || 0);
  }
  return String(a ?? "") === String(b ?? "");
}

function splitPayload(values) {
  const payload = {};
  const clear = [];
  const alwaysOverride = new Set(["multi_message", "reply_without_at", "proactive_enabled"]);
  for (const [key, val] of Object.entries(values)) {
    // 开关类字段必须显式保存，不能因为“和全局相同”就清成继承。
    // 否则全局开着主动话题时，群里关掉会被重新继承成开。
    if (!alwaysOverride.has(key) && sameVal(val, cfgVal(key))) clear.push(key);
    else payload[key] = val;
  }
  if (clear.length) payload.clear = clear;
  return payload;
}

function requireGroup() {
  const group = currentReplyGroup();
  if (!group) {
    $("rpGroupMsg").textContent = "还没有选中群，请先在「群聊与黑名单」里添加群";
    return "";
  }
  return group;
}

async function reloadGroupIfAny() {
  const group = currentReplyGroup();
  if (group) await loadGroupReply(group);
}

/* ---------------- 全局回复设置 ---------------- */
$("gReplySave").onclick = async () => {
  $("gReplySave").disabled = true;
  $("gReplyMsg").textContent = "保存中…";
  try {
    await api("/api/reply", { method: "POST", body: JSON.stringify({
      fallback_reply: $("gFallback").value,
      chunk_limit: Number($("gChunk").value) || 1200,
      max_chunks: Number($("gChunks").value) || 3,
      multi_message: $("gMulti").checked,
      multi_message_max: Number($("gMultiMax").value) || 3,
      multi_message_delay_ms: Number($("gMultiDelay").value) || 0,
      reply_without_at: $("gNoAt").checked,
    })});
    $("gReplyMsg").textContent = "已保存";
    filled.global = false;
    await refresh();
    await reloadGroupIfAny();
  } catch (e) { $("gReplyMsg").textContent = "保存失败：" + e.message; }
  finally { $("gReplySave").disabled = false; }
};

$("gLsSave").onclick = async () => {
  $("gLsSave").disabled = true;
  $("gLsMsg").textContent = "保存中…";
  try {
    await api("/api/settings", { method: "POST", body: JSON.stringify({
      listen_enabled: $("gLsOn").checked,
      listen_probability: Number($("gLsProb").value) || 0,
      listen_cooldown_s: Number($("gLsCooldown").value) || 0,
      listen_daily_limit: Number($("gLsDaily").value) || 0,
      listen_min_chars: Number($("gLsMinChars").value) || 1,
      listen_min_members: Number($("gLsMinMembers").value) || 0,
      listen_keywords: $("gLsKeywords").value
        .split(/[\n,，、]/).map(x => x.trim()).filter(Boolean),
    })});
    $("gLsMsg").textContent = "已保存";
    filled.global = false;
    await refresh();
    await reloadGroupIfAny();
  } catch (e) { $("gLsMsg").textContent = "保存失败：" + e.message; }
  finally { $("gLsSave").disabled = false; }
};

$("gPrSave").onclick = async () => {
  $("gPrSave").disabled = true;
  $("gPrMsg").textContent = "保存中…";
  try {
    await api("/api/settings", { method: "POST", body: JSON.stringify({
      proactive_enabled: $("gPrOn").checked,
      proactive_probability: Number($("gPrProb").value) || 0,
      proactive_interval_s: Number($("gPrInterval").value) || 0,
      proactive_idle_s: Number($("gPrIdle").value) || 0,
      proactive_daily_limit: Number($("gPrDaily").value) || 0,
      proactive_prompt: $("gPrPrompt").value,
    })});
    $("gPrMsg").textContent = "已保存";
    filled.global = false;
    await refresh();
    await reloadGroupIfAny();
  } catch (e) { $("gPrMsg").textContent = "保存失败：" + e.message; }
  finally { $("gPrSave").disabled = false; }
};

$("gPrOn").addEventListener("change", () => {
  $("gProactiveFields").style.display = $("gPrOn").checked ? "" : "none";
});

$("gReplyExport").onclick = async () => {
  try {
    const r = await api("/api/reply/export");
    $("gReplyMsg").textContent = "已导出到 " + r.path;
  } catch (e) { $("gReplyMsg").textContent = "导出失败：" + e.message; }
};

$("gReplyImportBtn").onclick = () => $("gReplyImport").click();
$("gReplyImport").addEventListener("change", async (e) => {
  const file = e.target.files && e.target.files[0];
  e.target.value = "";
  if (!file) return;
  try {
    const payload = JSON.parse(await file.text());
    await api("/api/reply/import", {
      method: "POST", body: JSON.stringify({ data: payload }),
    });
    $("gReplyMsg").textContent = "已导入";
    filled.global = false;
    await refresh();
    await reloadGroupIfAny();
  } catch (err) { $("gReplyMsg").textContent = "导入失败：" + err.message; }
});

/* ---------------- 分群回复设置 ---------------- */
$("rpSave").onclick = async () => {
  const group = requireGroup();
  if (!group) return;
  $("rpSave").disabled = true;
  $("rpMsg").textContent = "保存中…";
  try {
    const payload = splitPayload({
      fallback_reply: $("rpFallback").value,
      chunk_limit: Number($("rpChunk").value) || 1200,
      max_chunks: Number($("rpChunks").value) || 3,
      multi_message: $("rpMulti").checked,
      multi_message_max: Number($("rpMultiMax").value) || 3,
      multi_message_delay_ms: Number($("rpMultiDelay").value) || 0,
      reply_without_at: $("rpNoAt").checked,
    });
    await api(`/api/groups/${encodeURIComponent(group)}/reply`, {
      method: "POST", body: JSON.stringify(payload),
    });
    await loadGroupReply(group);
    $("rpMsg").textContent = "已保存；与全局相同的项已改为继承";
  } catch (e) { $("rpMsg").textContent = "保存失败：" + e.message; }
  finally { $("rpSave").disabled = false; }
};

$("lsSave").onclick = async () => {
  const group = requireGroup();
  if (!group) return;
  $("lsSave").disabled = true;
  $("lsMsg").textContent = "保存中…";
  try {
    const payload = splitPayload({
      listen_probability: Number($("lsProb").value) || 0,
      listen_cooldown_s: Number($("lsCooldown").value) || 0,
      listen_daily_limit: Number($("lsDaily").value) || 0,
      listen_min_chars: Number($("lsMinChars").value) || 1,
      listen_min_members: Number($("lsMinMembers").value) || 0,
      listen_keywords: $("lsKeywords").value
        .split(/[\n,，、]/).map(x => x.trim()).filter(Boolean),
    });
    payload.listen_enabled = $("lsOn").checked;
    await api(`/api/groups/${encodeURIComponent(group)}/reply`, {
      method: "POST", body: JSON.stringify(payload),
    });
    await loadGroupReply(group);
    const masterOn = !!(ST.config && ST.config.listen_enabled);
    $("lsMsg").textContent =
      $("lsOn").checked && !masterOn
        ? "已保存；但全局监听总开关未开启，本群仍不会接话"
        : "已保存；与全局相同的项已改为继承";
  } catch (e) { $("lsMsg").textContent = "保存失败：" + e.message; }
  finally { $("lsSave").disabled = false; }
};

$("gLsOn").addEventListener("change", () => {
  $("gListenFields").style.display = $("gLsOn").checked ? "" : "none";
});
$("lsOn").addEventListener("change", () => {
  $("listenFields").style.display = $("lsOn").checked ? "" : "none";
  updateListenMasterHint($("lsOn").checked);
});

$("rpRepeatSave").onclick = async () => {
  $("rpRepeatSave").disabled = true;
  $("rpRepeatMsg").textContent = "保存中…";
  try {
    await api("/api/settings", { method: "POST", body: JSON.stringify({
      repeat_probability: Number($("rpRepeatProb").value) || 0,
      repeat_cooldown_s: Number($("rpRepeatCooldown").value) || 0,
      repeat_daily_limit: Number($("rpRepeatDaily").value) || 0,
      repeat_max_chars: Number($("rpRepeatMax").value) || 40,
      repeat_mode: $("rpRepeatMode").value,
      repeat_prompt: $("rpRepeatPrompt").value,
    })});
    $("rpRepeatMsg").textContent = "已保存";
    filled.global = false;
    await refresh();
  } catch (e) { $("rpRepeatMsg").textContent = "保存失败：" + e.message; }
  finally { $("rpRepeatSave").disabled = false; }
};

function fillReplyFields(rs) {
  $("rpFallback").value = rs.fallback_reply || "";
  $("rpChunk").value = rs.chunk_limit ?? 1200;
  $("rpChunks").value = rs.max_chunks ?? 3;
  $("rpMulti").checked = !!rs.multi_message;
  $("rpMultiMax").value = rs.multi_message_max ?? 3;
  $("rpMultiDelay").value = rs.multi_message_delay_ms ?? 700;
  $("rpNoAt").checked = !!rs.reply_without_at;
  $("prActiveOn").checked = !!rs.proactive_enabled;
  $("proactiveFields").style.display = $("prActiveOn").checked ? "" : "none";
  $("prActiveProb").value = rs.proactive_probability ?? 10;
  $("prActiveInterval").value = rs.proactive_interval_s ?? 600;
  $("prActiveIdle").value = rs.proactive_idle_s ?? 300;
  $("prActiveDaily").value = rs.proactive_daily_limit ?? 5;
  $("prActivePrompt").value = rs.proactive_prompt || "";
  $("lsProb").value = rs.listen_probability ?? 15;
  $("lsCooldown").value = rs.listen_cooldown_s ?? 120;
  $("lsDaily").value = rs.listen_daily_limit ?? 30;
  $("lsMinChars").value = rs.listen_min_chars ?? 4;
  $("lsMinMembers").value = rs.listen_min_members ?? 0;
  $("lsKeywords").value = (rs.listen_keywords || []).join("\n");
}

const GROUP_FIELD_LABELS = {
  fallback_reply: "兜底话术",
  chunk_limit: "单条字数",
  max_chunks: "最多分条",
  multi_message: "分条发送",
  multi_message_max: "分条条数",
  multi_message_delay_ms: "分条间隔",
  reply_without_at: "回复不@",
  listen_probability: "接话概率",
  listen_cooldown_s: "接话冷却",
  listen_daily_limit: "接话每天上限",
  listen_min_chars: "最短字数",
  listen_min_members: "群人数下限",
  listen_keywords: "监听关键词",
  proactive_enabled: "主动话题开关",
  proactive_probability: "主动概率",
  proactive_interval_s: "主动冷却",
  proactive_idle_s: "安静时长",
  proactive_daily_limit: "主动每天上限",
  proactive_prompt: "主动提示词",
};

function updateListenMasterHint(groupListen) {
  const el = $("lsMasterWarn");
  if (!el) return;
  if (!ST || !ST.config) { el.style.display = "none"; return; }
  const master = !!ST.config.listen_enabled;
  const show = !!currentReplyGroup() && !!groupListen && !master;
  el.style.display = show ? "block" : "none";
  el.textContent = show
    ? "本群已勾选监听，但「全局回复设置」里的监听总开关没开，机器人仍然不会接话。"
      + "请到「全局回复设置 → 全局监听」勾选总开关并保存。"
    : "";
}

function updateProactiveMasterHint(groupOn) {
  const el = $("prMasterWarn");
  if (!el) return;
  if (!ST || !ST.config) { el.style.display = "none"; return; }
  const master = !!ST.config.proactive_enabled;
  const show = !!currentReplyGroup() && !!groupOn && !master;
  el.style.display = show ? "block" : "none";
  el.textContent = show
    ? "本群已启用主动话题，但「全局回复设置」里的主动话题总开关没开，仍然不会主动发言。"
      + "请到「全局回复设置 → 全局主动话题」勾选总开关并保存。"
    : "";
}

function updateGroupScope(overrides) {
  const keys = Object.keys(overrides || {});
  $("rpGroupScope").textContent = keys.length
    ? "本群已覆盖：" + keys.map(k => GROUP_FIELD_LABELS[k] || k).join("、")
    : "本群全部跟随全局回复设置";
}

async function loadGroupReply(group) {
  if (!group) {
    GROUP_REPLY_CURRENT = "";
    $("rpGroupScope").textContent = "";
    $("rpGroupMsg").textContent = "还没有群，请先在「群聊与黑名单」里添加";
    return;
  }
  GROUP_REPLY_CURRENT = group;
  $("rpGroupMsg").textContent = "加载中…";
  try {
    const data = await api(`/api/groups/${encodeURIComponent(group)}/reply`);
    fillReplyFields(data.effective || {});
    $("lsOn").checked = !!data.listen_enabled;
    $("listenFields").style.display = $("lsOn").checked ? "" : "none";
    updateGroupScope(data.overrides || {});
    updateListenMasterHint($("lsOn").checked);
    updateProactiveMasterHint($("prActiveOn").checked);
    $("rpGroupMsg").textContent = "已加载群设置";
  } catch (e) {
    $("rpGroupMsg").textContent = "加载失败：" + e.message;
  }
}

function currentReplyGroup() {
  return $("rpGroup").value || "";
}

function renderReplyGroups(groups) {
  const sel = $("rpGroup");
  const prev = sel.value || GROUP_REPLY_CURRENT;
  const options = [];
  groups.forEach(g => {
    const label = `群 ${g.group} · ${g.mode || "chat"}`;
    options.push(`<option value="${esc(g.group)}" title="${esc(g.group)}">${esc(label)}</option>`);
  });
  if (!options.length) {
    sel.innerHTML = `<option value="">（还没有群）</option>`;
    GROUP_REPLY_LOADED = true;
    loadGroupReply("");
    return;
  }
  sel.innerHTML = options.join("");
  const values = Array.from(sel.options).map(o => o.value);
  const wanted = prev && values.includes(prev) ? prev : values[0];
  sel.value = wanted;
  if (!GROUP_REPLY_LOADED || wanted !== GROUP_REPLY_CURRENT) {
    GROUP_REPLY_LOADED = true;
    loadGroupReply(wanted);
  }
}

$("rpGroup").addEventListener("change", () => loadGroupReply(currentReplyGroup()));

$("rpGroupExport").onclick = async () => {
  const group = requireGroup();
  if (!group) return;
  try {
    const r = await api(`/api/groups/${encodeURIComponent(group)}/reply/export`);
    $("rpGroupMsg").textContent = "已导出到 " + r.path;
  } catch (e) { $("rpGroupMsg").textContent = "导出失败：" + e.message; }
};

$("rpGroupImportBtn").onclick = () => $("rpGroupImport").click();
$("rpGroupImport").addEventListener("change", async (e) => {
  const file = e.target.files && e.target.files[0];
  e.target.value = "";
  if (!file) return;
  const group = requireGroup();
  if (!group) return;
  try {
    const payload = JSON.parse(await file.text());
    await api(`/api/groups/${encodeURIComponent(group)}/reply/import`, {
      method: "POST", body: JSON.stringify({ data: payload }),
    });
    await loadGroupReply(group);
    $("rpGroupMsg").textContent = "本群设置已导入";
  } catch (err) {
    $("rpGroupMsg").textContent = "导入失败：" + err.message;
  }
});

$("rpGroupReset").onclick = async () => {
  const group = requireGroup();
  if (!group) return;
  if (!confirm("清除这个群的所有覆盖，全部改回跟随全局回复设置？")) return;
  try {
    await api(`/api/groups/${encodeURIComponent(group)}/reply`, { method: "DELETE" });
    await loadGroupReply(group);
    $("rpGroupMsg").textContent = "已清除本群覆盖";
  } catch (e) { $("rpGroupMsg").textContent = "清除失败：" + e.message; }
};

$("prActiveOn").addEventListener("change", () => {
  $("proactiveFields").style.display = $("prActiveOn").checked ? "" : "none";
  updateProactiveMasterHint($("prActiveOn").checked);
});

$("pgOn").addEventListener("change", () => {
  $("personaFields").style.display = $("pgOn").checked ? "" : "none";
});

$("prActiveSave").onclick = async () => {
  const group = requireGroup();
  if (!group) return;
  $("prActiveSave").disabled = true;
  $("prActiveMsg").textContent = "保存中…";
  try {
    const payload = splitPayload({
      proactive_enabled: $("prActiveOn").checked,
      proactive_probability: Number($("prActiveProb").value) || 0,
      proactive_interval_s: Number($("prActiveInterval").value) || 0,
      proactive_idle_s: Number($("prActiveIdle").value) || 0,
      proactive_daily_limit: Number($("prActiveDaily").value) || 0,
      proactive_prompt: $("prActivePrompt").value,
    });
    await api(`/api/groups/${encodeURIComponent(group)}/reply`, {
      method: "POST", body: JSON.stringify(payload),
    });
    await loadGroupReply(group);
    $("prActiveMsg").textContent = "已保存；与全局相同的项已改为继承";
  } catch (e) { $("prActiveMsg").textContent = "保存失败：" + e.message; }
  finally { $("prActiveSave").disabled = false; }
};

$("prGroupPromptExport").onclick = async () => {
  const group = requireGroup();
  if (!group) return;
  try {
    const r = await api(`/api/groups/${encodeURIComponent(group)}/prompts/proactive/export`);
    $("prActiveMsg").textContent = "已导出到 " + r.path;
  } catch (e) { $("prActiveMsg").textContent = "导出失败：" + e.message; }
};

$("prGroupPromptImportBtn").onclick = () => $("prGroupPromptImport").click();
$("prGroupPromptImport").addEventListener("change", async (e) => {
  const file = e.target.files && e.target.files[0];
  e.target.value = "";
  if (!file) return;
  const group = requireGroup();
  if (!group) return;
  try {
    const payload = JSON.parse(await file.text());
    await api(`/api/groups/${encodeURIComponent(group)}/prompts/proactive/import`, {
      method: "POST", body: JSON.stringify({ data: payload }),
    });
    await loadGroupReply(group);
    $("prActiveMsg").textContent = "本群主动话题提示词已导入";
  } catch (err) {
    $("prActiveMsg").textContent = "导入失败：" + err.message;
  }
});

$("pgUseModel").addEventListener("change", () => {
  $("pgModelBox").style.display = $("pgUseModel").checked ? "" : "none";
  if ($("pgUseModel").checked) applyPgPreset(false);
});

function applyPgPreset(force) {
  const p = PRESETS.find(x => x.id === $("pgKind").value);
  $("pgExtraFields").style.display = $("pgKind").value ? "contents" : "none";
  if (!p) {
    $("pgNote").textContent = "沿用主模型的服务商和地址";
    $("pgBaseWrap").style.display = "none";
    $("pgModelPick").innerHTML = "";
    return;
  }
  $("pgExtraFields").style.display = "contents";
  $("pgNote").textContent = p.note || "";
  const isCustom = p.id === "custom";
  $("pgBaseWrap").style.display = isCustom ? "" : "none";
  if (isCustom) {
    if (force && !$("pgBase").value) $("pgBase").value = $("pvBase").value || "";
  } else if (p.base_url) {
    $("pgBase").value = p.base_url;
  }
  $("pgModelPick").innerHTML =
    `<option value="">从列表选择</option>` +
    (p.models || []).map(m => `<option value="${m}">${m}</option>`).join("");
  if (p.models && p.models.length) {
    if (force || !$("pgModel").value) $("pgModel").value = p.models[0];
    $("pgModelPick").value = p.models.includes($("pgModel").value)
      ? $("pgModel").value : p.models[0];
  }
}

$("pgKind").addEventListener("change", () => applyPgPreset(true));
$("pgModelPick").addEventListener("change", () => {
  if ($("pgModelPick").value) $("pgModel").value = $("pgModelPick").value;
});

$("pgFetchModels").onclick = async () => {
  $("pgFetchModels").disabled = true;
  try {
    const r = await api("/api/provider/models", { method: "POST", body: JSON.stringify({
      base_url: $("pgKind").value === "custom" ? $("pgBase").value.trim() : "",
      api_key: $("pgKey").value.trim(),
    })});
    const models = (r.models || []).filter(Boolean);
    $("pgModelPick").innerHTML =
      `<option value="">从列表选择</option>` +
      models.map(m => `<option value="${m}">${m}</option>`).join("");
    if (models.length && !models.includes($("pgModel").value)) {
      $("pgModel").value = models[0];
    }
    if ($("pgModel").value) $("pgModelPick").value = $("pgModel").value;
  } catch (e) {
    $("pgKeyHint").textContent = "拉取失败：" + e.message;
  } finally { $("pgFetchModels").disabled = false; }
};

$("pgCopy").onclick = () => {
  const mainKind = $("pvKind").value || "mock";
  $("pgKind").value = ["mock", "failing"].includes(mainKind) ? "" : mainKind;
  $("pgBase").value = $("pvBase").value || "";
  $("pgModel").value = $("pvModel").value || "";
  applyPgPreset(false);
};

function reportText(r) {
  const raw = String(r.note || "").trim();
  const fallback = Number(r.weight) || 0;
  if (!raw) return `- （无报告文字）（${fallback.toFixed(1)}）`;
  const lines = raw.split(/\r?\n/).map(x => x.trim()).filter(Boolean);
  const parsed = lines.map(line => {
    const m = line.match(/^(.*?)[（(]\s*([0-9]+(?:\.[0-9]+)?)\s*[）)]\s*$/);
    const value = m ? Number(m[2]) : NaN;
    const valid = m && value >= 0 && value <= 1;
    return {
      line,
      content: m ? m[1].trim() : line.replace(/^[-*•]\s*/, ""),
      weight: valid ? value : null,
    };
  });
  const anyValid = parsed.some(x => x.weight !== null);
  const hasParen = lines.some(x => /[（(].*[）)]/.test(x));
  if (!anyValid && fallback > 0 && !hasParen) {
    const body = parsed.map(x => x.content).join("\n");
    return `- ${body}（${fallback.toFixed(1)}）`;
  }
  return parsed.map(x => {
    const prefix = /^[-*•]/.test(x.line) ? x.line : "- " + x.line;
    if (x.weight === null) return prefix + "（不生效）";
    return prefix;
  }).join("\n");
}

function hasValidReportWeight(text) {
  return String(text || "").split(/\r?\n/).some(line => {
    const m = line.trim().match(/[（(]\s*([0-9]+(?:\.[0-9]+)?)\s*[）)]\s*$/);
    if (!m) return false;
    const value = Number(m[1]);
    return value >= 0 && value <= 1;
  });
}

function renderPersonaReports(force = false) {
  if (PERSONA_EDIT >= 0 && !force) return;
  if (PERSONA_EDIT >= PERSONA_REPORTS.length) PERSONA_EDIT = -1;
  $("pgReportsMsg").textContent =
    PERSONA_TOTAL ? `共 ${PERSONA_TOTAL} 条报告` : "";
  if (!PERSONA_REPORTS.length) {
    $("pgReports").innerHTML =
      `<span class="hint">还没有自检报告。启用后达到自检条数会自动产生，也可以点「立即自检」。</span>`;
    renderPager("pgReportsPager", 1, 1, "reports");
    return;
  }
  const rows = PERSONA_REPORTS.map((r, i) => {
    const time = new Date((r.ts || 0) * 1000).toLocaleString();
    const status = r.status === "drift" ? "drift"
      : r.status === "error" ? "error" : "ok";
    const label = status === "drift" ? "跑偏"
      : status === "error" ? "异常" : "正常";
    const cls = status === "drift" ? "disabled"
      : status === "error" ? "disabled" : "active";
    const source = r.source === "manual" ? "手动" : "自动";
    const head = `<div class="memrow2">
        <code style="color:#8b93a1">群…${esc(String(r.group || "").slice(-8))}</code>
        <span class="tag mode">${esc(r.mode || "chat")}</span>
        <span class="tag ${cls}">${label}</span>
        <span class="hint">${source} · ${esc(time)}</span>
      </div>`;
    if (i === PERSONA_EDIT) {
      return `<div class="memitem">
        ${head}
        <div class="memtextrow">
          <div style="flex:1;min-width:0">
            <textarea id="pnote-${i}" rows="4" maxlength="500" style="width:100%"
              placeholder="每行一条，格式：- 问题内容（权重）；括号缺失或数值不合法则不生效">${esc(r.note || "")}</textarea>
          </div>
          <div class="memactions">
            <button class="mini" data-psave="${i}">保存</button>
            <button class="mini ghost" data-pcancel="${i}">取消</button>
            <span id="pmsg-${i}" class="hint"></span>
          </div>
        </div>
      </div>`;
    }
    return `<div class="memitem">
      ${head}
      <div class="memtextrow">
        <div class="memtext">${esc(reportText(r))}</div>
        <div class="memactions">
          <button class="mini ghost" data-pedit="${i}">编辑</button>
          <button class="mini ghost" data-pdelete="${i}">删除</button>
          <button class="mini ghost" data-pclear="${i}">清空本群</button>
        </div>
      </div>
    </div>`;
  }).join("");
  $("pgReports").innerHTML = `<div class="memlist">${rows}</div>`;
  renderPager("pgReportsPager", PERSONA_PAGE, PERSONA_PAGES, "reports");
}

async function loadReportsPage(page) {
  if (PERSONA_EDIT >= 0) return;
  try {
    const r = await api(`/api/persona/reports/page?page=${page}&size=${PERSONA_PAGE_SIZE}`);
    PERSONA_REPORTS = r.items || [];
    PERSONA_PAGE = r.page || 1;
    PERSONA_PAGES = r.pages || 1;
    PERSONA_TOTAL = r.total || 0;
    renderPersonaReports();
  } catch (e) { /* 保持当前页 */ }
}

$("pgReports").addEventListener("click", async (e) => {
  const edit = e.target.closest("[data-pedit]");
  if (edit) {
    PERSONA_EDIT = Number(edit.getAttribute("data-pedit"));
    renderPersonaReports(true);
    return;
  }
  const cancel = e.target.closest("[data-pcancel]");
  if (cancel) {
    PERSONA_EDIT = -1;
    renderPersonaReports(true);
    return;
  }
  const save = e.target.closest("[data-psave]");
  if (!save) return;
  const idx = Number(save.getAttribute("data-psave"));
  const report = PERSONA_REPORTS[idx];
  if (!report) return;
  const note = $("pnote-" + idx).value;
  if (note.trim() && !hasValidReportWeight(note)) {
    if (!confirm("没有检测到合法权重，保存后这条报告不会影响回复。仍要保存吗？")) return;
  }
  save.disabled = true;
  $("pmsg-" + idx).textContent = "保存中…";
  try {
    const r = await api("/api/persona/reports/item", {
      method: "POST", body: JSON.stringify({
        id: report.id, note,
      }),
    });
    PERSONA_EDIT = -1;
    PERSONA_PAGE = 1;
    await loadReportsPage(1);
    $("pgReportsMsg").textContent += " · 已保存";
  } catch (err) {
    $("pmsg-" + idx).textContent =
      (String(err.message || "").includes("没有找到"))
        ? "报告已被删除或裁剪，内容仍保留，请复制后处理"
        : "保存失败：" + err.message;
  } finally {
    save.disabled = false;
  }
});

$("pgReports").addEventListener("click", async (e) => {
  const clear = e.target.closest("[data-pclear]");
  if (clear) {
    const idx = Number(clear.getAttribute("data-pclear"));
    const report = PERSONA_REPORTS[idx];
    if (!report) return;
    if (!confirm(`清空群…${String(report.group || "").slice(-8)} 的全部自检报告？`)) return;
    clear.disabled = true;
    try {
      const r = await api("/api/persona/reports/clear", {
        method: "POST", body: JSON.stringify({ group: report.group }),
      });
      PERSONA_EDIT = -1;
      PERSONA_PAGE = 1;
      await loadReportsPage(1);
      $("pgReportsMsg").textContent += ` · 已清空 ${Number(r.removed) || 0} 条`;
    } catch (err) {
      $("pgReportsMsg").textContent = "清空失败：" + err.message;
    } finally {
      clear.disabled = false;
    }
    return;
  }
  const del = e.target.closest("[data-pdelete]");
  if (!del) return;
  const idx = Number(del.getAttribute("data-pdelete"));
  const report = PERSONA_REPORTS[idx];
  if (!report) return;
  if (!confirm(`删除群…${String(report.group || "").slice(-8)} 的这条自检报告？`)) return;
  del.disabled = true;
  try {
    const r = await api("/api/persona/reports/item/delete", {
      method: "POST", body: JSON.stringify({ id: report.id }),
    });
    PERSONA_EDIT = -1;
    await loadReportsPage(PERSONA_PAGE);
    $("pgReportsMsg").textContent += " · 已删除";
  } catch (err) {
    $("pgReportsMsg").textContent = "删除失败：" + err.message;
  } finally {
    del.disabled = false;
  }
});

$("pgReportsPager").addEventListener("click", async (e) => {
  const b = e.target.closest("[data-pager]");
  if (!b || PERSONA_EDIT >= 0) return;
  PERSONA_PAGE += Number(b.dataset.dir) || 0;
  await loadReportsPage(PERSONA_PAGE);
});

$("pgSave").onclick = async () => {
  $("pgSave").disabled = true;
  $("pgMsg").textContent = "保存中…";
  try {
    await api("/api/settings", { method: "POST", body: JSON.stringify({
      persona_anchor: $("pgAnchor").value,
      persona_guard_enabled: $("pgOn").checked,
      persona_check_interval: Number($("pgCheck").value) || 0,
      persona_check_use_separate: $("pgUseModel").checked,
      persona_check_provider: $("pgKind").value,
      persona_check_base_url: $("pgBase").value,
      persona_check_model: $("pgModel").value,
      persona_check_api_key: $("pgKey").value,
    })});
    $("pgMsg").textContent = "已保存";
    filled.persona = false;
    filled.global = false;
    await refresh();
  } catch (e) { $("pgMsg").textContent = "保存失败：" + e.message; }
  finally { $("pgSave").disabled = false; }
};

async function exportPrompt(key, msgId) {
  try {
    const r = await api(`/api/prompts/${encodeURIComponent(key)}/export`);
    $(msgId).textContent = "已导出到 " + r.path;
  } catch (e) {
    $(msgId).textContent = "导出失败：" + e.message;
  }
}

async function importPrompt(key, inputId, msgId) {
  const file = $(inputId).files && $(inputId).files[0];
  if (!file) return;
  try {
    const payload = JSON.parse(await file.text());
    const r = await api(`/api/prompts/${encodeURIComponent(key)}/import`, {
      method: "POST", body: JSON.stringify({ data: payload }),
    });
    $(msgId).textContent = `已导入（${(r.text || "").length} 字）`;
    filled.global = false;
    if (key === "persona_anchor") filled.persona = false;
    await refresh();
  } catch (e) {
    $(msgId).textContent = "导入失败：" + e.message;
  } finally {
    $(inputId).value = "";
  }
}

$("rpPromptExport").onclick = () => exportPrompt("repeat", "rpRepeatMsg");
$("rpPromptImportBtn").onclick = () => $("rpPromptImport").click();
$("rpPromptImport").addEventListener("change", () =>
  importPrompt("repeat", "rpPromptImport", "rpRepeatMsg"));

$("prPromptExport").onclick = () => exportPrompt("proactive", "gPrMsg");
$("prPromptImportBtn").onclick = () => $("prPromptImport").click();
$("prPromptImport").addEventListener("change", () =>
  importPrompt("proactive", "prPromptImport", "gPrMsg"));

$("pgPromptExport").onclick = () => exportPrompt("persona_anchor", "pgMsg");
$("pgPromptImportBtn").onclick = () => $("pgPromptImport").click();
$("pgPromptImport").addEventListener("change", () =>
  importPrompt("persona_anchor", "pgPromptImport", "pgMsg"));

$("pgCheckNow").onclick = async () => {
  $("pgCheckNow").disabled = true;
  $("pgCheckMsg").textContent = "自检中…";
  try {
    const r = await api("/api/persona/check", {
      method: "POST", body: JSON.stringify({}),
    });
    if (!r.ok) {
      $("pgCheckMsg").textContent = "自检失败：" + (r.error || "未知错误");
      if (r.reports) await loadReportsPage(PERSONA_PAGE);
      return;
    }
    const label = r.status === "drift" ? "跑偏"
      : r.status === "error" ? "异常" : "正常";
    $("pgCheckMsg").textContent =
      `已自检：${label}（权重 ${(Number(r.weight) || 0).toFixed(1)}）` +
      ` · 群…${String(r.group || "").slice(-8)} / ${String(r.mode || "chat")}` +
      (r.note ? ` · ${r.note}` : "");
    PERSONA_PAGE = 1;
    await loadReportsPage(1);
  } catch (e) {
    $("pgCheckMsg").textContent = "自检失败：" + e.message;
  } finally {
    $("pgCheckNow").disabled = false;
  }
};

$("pgReportsExport").onclick = async () => {
  try {
    const r = await api("/api/persona/reports/export");
    $("pgReportsFileMsg").textContent = "已导出到 " + r.path;
  } catch (e) { $("pgReportsFileMsg").textContent = "导出失败：" + e.message; }
};

$("pgReportsImportBtn").onclick = () => $("pgReportsImport").click();
$("pgReportsImport").addEventListener("change", async (e) => {
  const file = e.target.files && e.target.files[0];
  e.target.value = "";
  if (!file) return;
  try {
    const payload = JSON.parse(await file.text());
    const mode = $("pgReportsImportMode").value || "merge";
    if (mode === "replace" && !confirm("覆盖导入会删除当前全部自检报告，确定继续吗？")) return;
    const r = await api("/api/persona/reports/import", {
      method: "POST", body: JSON.stringify({ data: payload, mode }),
    });
    $("pgReportsFileMsg").textContent =
      `已导入（${mode === "replace" ? "覆盖" : "合并"}，新增 ${Number(r.added) || 0} 条）`;
    PERSONA_PAGE = 1;
    await refresh();
    await loadReportsPage(1);
  } catch (err) {
    $("pgReportsFileMsg").textContent = "导入失败：" + err.message;
  }
});

/* ---------------- 关键词规则 ---------------- */
function esc(s) {
  return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function renderRules() {
  $("rules").innerHTML = RULES.length
    ? RULES.map((r, i) => `
      <div style="border:1px solid #262a31;border-radius:8px;padding:10px;margin-bottom:8px">
        <div style="display:flex;gap:8px;align-items:center">
          <input data-i="${i}" data-f="pattern" value="${esc(r.pattern)}"
                 placeholder="正则，例如 开团|跑团|怎么玩" style="flex:1">
          <label style="display:flex;align-items:center;gap:6px;margin:0;white-space:nowrap">
            <input type="checkbox" data-i="${i}" data-f="enabled" ${r.enabled ? "checked" : ""}
                   style="width:auto">启用
          </label>
          <button class="mini ghost" data-del="${i}">删除</button>
        </div>
        <textarea data-i="${i}" data-f="reply" rows="2" style="margin-top:8px"
          placeholder="命中后回复的固定内容">${esc(r.reply)}</textarea>
      </div>`).join("")
    : `<span class="hint">还没有规则</span>`;
}

$("rules").addEventListener("input", (e) => {
  const el = e.target.closest("[data-i]");
  if (!el) return;
  const i = Number(el.dataset.i), f = el.dataset.f;
  if (!RULES[i]) return;
  RULES[i][f] = f === "enabled" ? el.checked : el.value;
});

$("rules").addEventListener("click", (e) => {
  const b = e.target.closest("[data-del]");
  if (!b) return;
  RULES.splice(Number(b.dataset.del), 1);
  renderRules();
});

$("ruleAdd").onclick = () => {
  if (RULES.length >= 50) return alert("最多 50 条");
  RULES.push({ pattern: "", reply: "", enabled: true });
  renderRules();
};

$("ruleSave").onclick = async () => {
  $("ruleSave").disabled = true;
  $("ruleMsg").textContent = "保存中…";
  try {
    const r = await api("/api/rules", { method: "POST", body: JSON.stringify({ rules: RULES }) });
    RULES = (r.rules || []).map(x => ({ ...x }));
    renderRules();
    $("ruleMsg").textContent = `已保存 ${RULES.length} 条`;
  } catch (e) { $("ruleMsg").textContent = "保存失败：" + e.message; }
  finally { $("ruleSave").disabled = false; }
};

$("ruleExport").onclick = async () => {
  try {
    const r = await api("/api/keywords/export");
    $("ruleFileMsg").textContent = "已导出到 " + r.path;
  } catch (e) { $("ruleFileMsg").textContent = "导出失败：" + e.message; }
};

$("ruleImportBtn").onclick = () => $("ruleImport").click();
$("ruleImport").addEventListener("change", async (e) => {
  const file = e.target.files && e.target.files[0];
  e.target.value = "";
  if (!file) return;
  try {
    const payload = JSON.parse(await file.text());
    const r = await api("/api/keywords/import", {
      method: "POST", body: JSON.stringify({ data: payload }),
    });
    RULES = (r.rules || []).map(rule => ({
      pattern: rule.pattern || "",
      reply: rule.reply || "",
      enabled: rule.enabled !== false,
    }));
    renderRules();
    $("ruleFileMsg").textContent = `已导入 ${RULES.length} 条`;
  } catch (err) {
    $("ruleFileMsg").textContent = "导入失败：" + err.message;
  }
});

/* ---------------- 人设导入导出 ---------------- */
$("psExport").onclick = async () => {
  try {
    const r = await api("/api/persona/export");
    $("psMsg").textContent = "已导出到 " + r.path;
  } catch (e) { $("psMsg").textContent = "导出失败：" + e.message; }
};

$("psImportBtn").onclick = () => $("psImport").click();

$("psImport").addEventListener("change", async (e) => {
  const f = e.target.files && e.target.files[0];
  e.target.value = "";
  if (!f) return;
  try {
    const text = await f.text();
    const payload = JSON.parse(text);
    await api("/api/persona/import", { method: "POST", body: JSON.stringify({ data: payload }) });
    filled.persona = false;
    await refresh();
    $("psMsg").textContent = "已导入：" + f.name;
  } catch (err) { $("psMsg").textContent = "导入失败：" + err.message; }
});

$("groups").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-gl]");
  if (!btn) return;
  const enable = btn.dataset.on === "1";
  btn.disabled = true;
  try {
    await api(`/api/groups/${encodeURIComponent(btn.dataset.gl)}/listen`, {
      method: "POST", body: JSON.stringify({ enabled: enable }),
    });
    await refresh();
  } catch (err) {
    btn.disabled = false;
    alert("切换监听失败：" + err.message);
  }
});

$("groups").addEventListener("change", async (e) => {
  const memberInput = e.target.closest("input[data-gn]");
  if (memberInput) {
    memberInput.disabled = true;
    try {
      await api(`/api/groups/${encodeURIComponent(memberInput.dataset.gn)}/members`, {
        method: "POST", body: JSON.stringify({ count: Number(memberInput.value) || 0 }),
      });
      await refresh();
    } catch (err) {
      memberInput.disabled = false;
      alert("保存人数失败：" + err.message);
    }
    return;
  }
  const ruleSel = e.target.closest("select[data-gr]");
  const packSel = e.target.closest("select[data-gp]");
  const modeSel = e.target.closest("select[data-gm]");
  const sel = ruleSel || packSel || modeSel;
  if (!sel) return;
  sel.disabled = true;
  try {
    if (ruleSel) {
      await api(`/api/groups/${encodeURIComponent(sel.dataset.gr)}/rule`,
                { method: "POST", body: JSON.stringify({ house_rule: sel.value }) });
    } else if (packSel) {
      await api(`/api/groups/${encodeURIComponent(sel.dataset.gp)}/rulepack`,
                { method: "POST", body: JSON.stringify({ rulepack: sel.value }) });
    } else {
      await api(`/api/groups/${encodeURIComponent(sel.dataset.gm)}/mode`,
                { method: "POST", body: JSON.stringify({ mode: sel.value }) });
    }
    await refresh();
  } catch (err) { alert("切换失败：" + err.message); }
  finally { sel.disabled = false; }
});

$("groups").addEventListener("click", async (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  if (b.dataset.copy) {
    const ok = await copyText(b.dataset.copy);
    if (!ok) {
      alert("复制失败，请手动选中群号复制");
      return;
    }
    b.textContent = "已复制";
    setTimeout(() => { b.textContent = "复制"; }, 1200);
    return;
  }
  b.disabled = true;
  try {
    if (b.dataset.s) {
      await api(`/api/groups/${encodeURIComponent(b.dataset.g)}/status`,
                { method: "POST", body: JSON.stringify({ status: b.dataset.s }) });
    }
    await refresh();
  } catch (err) { alert("操作失败：" + err.message); b.disabled = false; }
});

$("mutedBox").addEventListener("click", async (e) => {
  const b = e.target.closest("button[data-unmute-m]");
  if (!b) return;
  b.disabled = true;
  try {
    await api("/api/abuse/unmute", { method: "POST",
      body: JSON.stringify({ group: b.dataset.unmuteG, member: b.dataset.unmuteM }) });
    await refresh();
  } catch (err) { alert("解封失败：" + err.message); b.disabled = false; }
});

$("diag").onclick = async () => {
  try {
    const r = await api("/api/diagnostics", { method: "POST" });
    alert("已导出：\n" + r.path + "\n\n" + Math.round(r.size/1024) + " KB");
  } catch (e) { alert("导出失败：" + e.message); }
};

$("packReload").onclick = async () => {
  $("packReload").disabled = true;
  try {
    await api("/api/packs/reload", { method: "POST" });
    filled.plugins = false;
    await refresh();
    $("packMsg").textContent = "已重新扫描";
  } catch (e) {
    $("packMsg").textContent = "重新扫描失败：" + e.message;
  } finally { $("packReload").disabled = false; }
};

$("packTemplate").href = "/api/rulepacks/template?t=" + encodeURIComponent(TOKEN);

$("packList").addEventListener("click", async (e) => {
  const packBtn = e.target.closest("button[data-pack]");
  if (packBtn) {
    const enable = packBtn.dataset.on === "1";
    packBtn.disabled = true;
    try {
      const r = await api(`/api/rulepacks/${encodeURIComponent(packBtn.dataset.pack)}/enable`, {
        method: "POST", body: JSON.stringify({ enabled: enable }),
      });
      filled.plugins = false;
      await refresh();
      $("packMsg").textContent = enable ? "规则已启用" : "规则已关闭";
    } catch (err) {
      $("packMsg").textContent = "操作失败：" + err.message;
      packBtn.disabled = false;
    }
    return;
  }

  const btn = e.target.closest("button[data-hook]");
  if (!btn) return;
  const enable = btn.dataset.on === "1";
  if (enable && !confirm("启用后，这个规则文件里的 hook 会在子进程沙箱中执行。确认启用？")) return;
  btn.disabled = true;
  try {
    const r = await api(`/api/rulepacks/${encodeURIComponent(btn.dataset.hook)}/hooks`, {
      method: "POST", body: JSON.stringify({ enabled: enable }),
    });
    filled.plugins = false;
    await refresh();
    $("packMsg").textContent = enable ? "hook 已启用" : "hook 已关闭";
    if (r.pack_errors && r.pack_errors.length) {
      $("packMsg").textContent += "（有加载错误，见下方列表）";
    }
  } catch (err) {
    $("packMsg").textContent = "操作失败：" + err.message;
    btn.disabled = false;
  }
});

$("packImport").onclick = () => $("packFile").click();

$("packFile").onchange = async () => {
  const file = $("packFile").files[0];
  if (!file) return;
  $("packImport").disabled = true;
  $("packMsg").textContent = "读取中…";
  try {
    const source = await file.text();
    const send = (overwrite) => api("/api/rulepacks/import", {
      method: "POST",
      body: JSON.stringify({ filename: file.name, source, overwrite }),
    });
    let r;
    try {
      r = await send(false);
    } catch (e) {
      if (!/已存在/.test(e.message)) throw e;
      if (!confirm(`规则 ${file.name} 已存在，覆盖吗？`)) return;
      r = await send(true);
    }
    filled.plugins = false;
    await refresh();
    $("packMsg").textContent = `已导入 ${r.name}（${r.fields} 个字段，${r.checks} 套检定）`;
  } catch (e) {
    $("packMsg").textContent = "导入失败：" + e.message;
  } finally {
    $("packFile").value = "";
    $("packImport").disabled = false;
  }
};

$("modeTemplate").href = "/api/modes/template?t=" + encodeURIComponent(TOKEN);

$("modeScan").onclick = async () => {
  $("modeScan").disabled = true;
  $("modeMsg").textContent = "扫描中…";
  try {
    const r = await api("/api/modes/scan", { method: "POST" });
    renderModes(r);
    $("modeMsg").textContent = `共 ${(r.modes || []).length} 个模式`;
  } catch (e) {
    $("modeMsg").textContent = "扫描失败：" + e.message;
  } finally { $("modeScan").disabled = false; }
};

$("modeImport").onclick = () => $("modeFile").click();

$("modeFile").onchange = async () => {
  const file = $("modeFile").files[0];
  if (!file) return;
  $("modeImport").disabled = true;
  $("modeMsg").textContent = "读取中…";
  try {
    const source = await file.text();
    const send = (overwrite) => api("/api/modes/import", {
      method: "POST",
      body: JSON.stringify({ filename: file.name, source, overwrite }),
    });
    let r;
    try {
      r = await send(false);
    } catch (e) {
      if (!/已存在/.test(e.message)) throw e;
      if (!confirm(`模式 ${file.name} 已存在，覆盖吗？`)) return;
      r = await send(true);
    }
    filled.plugins = false;
    await refresh();
    $("modeMsg").textContent = `已导入「${r.label}」` +
      (r.call_llm ? "（会调用模型）" : "（不调用模型）");
  } catch (e) {
    $("modeMsg").textContent = "导入失败：" + e.message;
  } finally {
    $("modeFile").value = "";
    $("modeImport").disabled = false;
  }
};

$("gameTemplate").href = "/api/minigames/template?t=" + encodeURIComponent(TOKEN);

$("gameScan").onclick = async () => {
  $("gameScan").disabled = true;
  $("gameMsg").textContent = "扫描中…";
  try {
    const r = await api("/api/minigames/scan", { method: "POST" });
    renderGames(r);
    $("gameMsg").textContent = `找到 ${(r.games || []).length} 个游戏`;
  } catch (e) {
    $("gameMsg").textContent = "扫描失败：" + e.message;
  } finally { $("gameScan").disabled = false; }
};

$("gameImport").onclick = () => $("gameFile").click();

$("gameFile").onchange = async () => {
  const file = $("gameFile").files[0];
  if (!file) return;
  $("gameImport").disabled = true;
  $("gameMsg").textContent = "读取中…";
  try {
    const source = await file.text();
    const send = (overwrite) => api("/api/minigames/import", {
      method: "POST",
      body: JSON.stringify({ filename: file.name, source, overwrite }),
    });
    let r;
    try {
      r = await send(false);
    } catch (e) {
      if (!/已存在/.test(e.message)) throw e;
      if (!confirm(`游戏 ${file.name} 已存在，覆盖吗？`)) return;
      r = await send(true);
    }
    filled.plugins = false;
    await refresh();
    $("gameMsg").textContent = `已导入 ${r.name}（指令 ${r.commands.join(" ")}）`;
  } catch (e) {
    $("gameMsg").textContent = "导入失败：" + e.message;
  } finally {
    $("gameFile").value = "";
    $("gameImport").disabled = false;
  }
};

$("gameList").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-game]");
  if (!btn) return;
  const enable = btn.dataset.on === "1";
  btn.disabled = true;
  btn.textContent = enable ? "启用中…" : "关闭中…";
  try {
    const r = await api(`/api/minigames/${encodeURIComponent(btn.dataset.game)}/enable`, {
      method: "POST", body: JSON.stringify({ enabled: enable }),
    });
    filled.plugins = false;
    await refresh();
    $("gameMsg").textContent = enable ? "已启用，可以直接发指令了" : "已关闭";
  } catch (err) {
    $("gameMsg").textContent = "操作失败：" + err.message;
    btn.disabled = false;
    btn.textContent = enable ? "启用" : "关闭";
  }
});

$("codePluginScan").onclick = async () => {
  $("codePluginScan").disabled = true;
  $("codePluginMsg").textContent = "扫描中…";
  try {
    const r = await api("/api/code-plugins/scan", { method: "POST" });
    renderCodePlugins(r);
    $("codePluginMsg").textContent = `找到 ${(r.plugins || []).length} 个插件`;
  } catch (e) {
    $("codePluginMsg").textContent = "扫描失败：" + e.message;
  } finally { $("codePluginScan").disabled = false; }
};

$("codePlugins").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-plug]");
  if (!btn) return;
  const enable = btn.dataset.on === "1";
  btn.disabled = true;
  btn.textContent = enable ? "启用中…" : "关闭中…";
  try {
    const r = await api(`/api/code-plugins/${encodeURIComponent(btn.dataset.plug)}/enable`, {
      method: "POST", body: JSON.stringify({ enabled: enable }),
    });
    renderCodePlugins(r);
    $("codePluginMsg").textContent = enable
      ? "已启用，指令立即可用"
      : "已关闭";
  } catch (err) {
    $("codePluginMsg").textContent = "操作失败：" + err.message;
    btn.disabled = false;
    btn.textContent = enable ? "启用" : "关闭";
  }
});

$("pvSend").onclick = doPreview;
$("pvInput").addEventListener("keydown", (e) => { if (e.key === "Enter") doPreview(); });
$("pvReset").onclick = async () => {
  try { await api("/api/chat/preview/reset", { method: "POST" }); } catch (e) { /* 忽略 */ }
  CHAT = [];
  renderChat();
  CHAT.push({ role: "sys", text: "上下文已清空" });
  renderChat();
};

async function refreshLogs() {
  try {
    const r = await api("/api/logs?lines=100");
    $("logs").textContent = (r.lines || []).join("\n") || "（空）";
    $("logs").scrollTop = $("logs").scrollHeight;
  } catch (e) { /* 忽略 */ }
}

$("logClear").onclick = async () => {
  if (!confirm("确定清空日志吗？清空后无法恢复。")) return;
  $("logClear").disabled = true;
  $("logMsg").textContent = "清空中…";
  try {
    const r = await api("/api/logs/clear", { method: "POST" });
    await refreshLogs();
    $("logMsg").textContent = `已清空（写入中 ${r.truncated} 个，删除旧文件 ${r.removed} 个）`;
  } catch (e) {
    $("logMsg").textContent = "清空失败：" + e.message;
  } finally {
    $("logClear").disabled = false;
  }
};

$("auditPrune").onclick = async () => {
  const keep = prompt(
    "保留最近多少天的审计记录？输入 0 表示全部清空。",
    String((ST.config && ST.config.audit_keep_days) ?? 30)
  );
  if (keep === null) return;
  const days = Number(keep);
  if (!Number.isFinite(days) || days < 0) {
    $("logMsg").textContent = "请输入 0 或正数";
    return;
  }
  const ask = days === 0
    ? "确定清空全部审计记录？"
    : `确定删除 ${days} 天前的审计记录？`;
  if (!confirm(ask)) return;
  $("auditPrune").disabled = true;
  $("logMsg").textContent = "清理中…";
  try {
    const r = await api("/api/audit/prune", {
      method: "POST", body: JSON.stringify({ keep_days: days }),
    });
    $("logMsg").textContent = `已清理 ${r.deleted} 条`;
    await refresh();
  } catch (e) {
    $("logMsg").textContent = "清理失败：" + e.message;
  } finally {
    $("auditPrune").disabled = false;
  }
};

$("backupBtn").href = "/api/backup?t=" + encodeURIComponent(TOKEN);

$("restoreBtn").onclick = () => $("restoreFile").click();

$("restoreFile").onchange = async () => {
  const file = $("restoreFile").files[0];
  if (!file) return;
  if (!confirm("恢复备份会覆盖当前群、角色卡、记忆和插件，继续吗？")) return;
  $("dataMsg").textContent = "恢复中…";
  try {
    const res = await fetch("/api/backup/restore", {
      method: "POST",
      headers: { "X-Token": TOKEN, "Content-Type": "application/zip" },
      body: await file.arrayBuffer(),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.error || body.detail || res.status);
    }
    alert("恢复完成，建议重启程序。");
    location.reload();
  } catch (e) {
    $("dataMsg").textContent = "恢复失败：" + e.message;
  } finally {
    $("restoreFile").value = "";
  }
};

$("resetData").onclick = async () => {
  const word = prompt("这会清空所有群、角色卡、记忆和日志，但保留账号配置和插件。\n输入 RESET 确认：");
  if (word !== "RESET") return;
  $("resetData").disabled = true;
  $("dataMsg").textContent = "清空中…";
  try {
    await api("/api/data/reset", { method: "POST", body: JSON.stringify({ confirm: "RESET" }) });
    alert("业务数据已清空。");
    location.reload();
  } catch (e) {
    $("dataMsg").textContent = "清空失败：" + e.message;
  } finally {
    $("resetData").disabled = false;
  }
};

renderSettings();
CHAT = [];
renderChat();
// 打开或刷新页面即清空试聊上下文，且试聊从不写入长期记忆
api("/api/chat/preview/reset", { method: "POST" }).catch(() => {});
loadPresets().then(refresh).catch(refresh).then(() => {
  loadMemoryPage(1);
  loadReportsPage(1);
});
refreshLogs();
setInterval(refresh, 2500);
setInterval(refreshLogs, 5000);
</script>
</body>
</html>
"""
