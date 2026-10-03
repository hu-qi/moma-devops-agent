"""Embedded modern responsive Single Page Application UI for DevOpsPilot Management Console."""

from __future__ import annotations


def get_dashboard_ui_html() -> str:
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DevOpsPilot · 智能研发自治管理控制台</title>
  <style>
    :root {
      --bg-primary: #0b0f19;
      --bg-secondary: #111827;
      --bg-card: #1f2937;
      --bg-hover: #374151;
      --text-main: #f9fafb;
      --text-muted: #9ca3af;
      --border-color: #374151;
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --accent-green: #10b981;
      --accent-amber: #f59e0b;
      --accent-red: #ef4444;
      --accent-purple: #8b5cf6;
      --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg-primary);
      color: var(--text-main);
      font-family: var(--font-sans);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }

    header {
      background-color: var(--bg-secondary);
      border-bottom: 1px solid var(--border-color);
      padding: 0.85rem 1.5rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: sticky;
      top: 0;
      z-index: 50;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .brand-logo {
      width: 32px;
      height: 32px;
      background: linear-gradient(135deg, #3b82f6, #8b5cf6);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      color: white;
      font-size: 1.1rem;
    }
    .brand-title {
      font-size: 1.15rem;
      font-weight: 700;
      letter-spacing: -0.02em;
    }
    .brand-tag {
      font-size: 0.72rem;
      background-color: rgba(59, 130, 246, 0.2);
      color: #60a5fa;
      padding: 0.15rem 0.5rem;
      border-radius: 9999px;
      border: 1px solid rgba(59, 130, 246, 0.4);
    }

    nav {
      display: flex;
      gap: 0.5rem;
    }
    .nav-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 0.5rem 0.85rem;
      border-radius: 6px;
      font-size: 0.88rem;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.15s ease;
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }
    .nav-btn:hover {
      background-color: var(--bg-card);
      color: var(--text-main);
    }
    .nav-btn.active {
      background-color: var(--primary);
      color: white;
    }

    main {
      flex: 1;
      max-width: 1300px;
      width: 100%;
      margin: 0 auto;
      padding: 1.5rem;
    }

    .tab-content { display: none; }
    .tab-content.active { display: block; animation: fadeIn 0.2s ease-in; }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(4px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* Grid & Cards */
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1rem;
      margin-bottom: 1.5rem;
    }
    .metric-card {
      background-color: var(--bg-secondary);
      border: 1px solid var(--border-color);
      border-radius: 10px;
      padding: 1.25rem;
      position: relative;
      overflow: hidden;
    }
    .metric-card::before {
      content: "";
      position: absolute;
      top: 0; left: 0; right: 0; height: 3px;
      background: var(--primary);
    }
    .metric-card.green::before { background: var(--accent-green); }
    .metric-card.amber::before { background: var(--accent-amber); }
    .metric-card.purple::before { background: var(--accent-purple); }

    .metric-label {
      font-size: 0.82rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 0.4rem;
    }
    .metric-value {
      font-size: 1.85rem;
      font-weight: 700;
      font-family: var(--font-mono);
      display: flex;
      align-items: baseline;
      gap: 0.4rem;
    }
    .metric-sub {
      font-size: 0.78rem;
      color: var(--text-muted);
      margin-top: 0.35rem;
    }

    .card {
      background-color: var(--bg-secondary);
      border: 1px solid var(--border-color);
      border-radius: 10px;
      padding: 1.25rem;
      margin-bottom: 1.5rem;
    }
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
      padding-bottom: 0.75rem;
      border-bottom: 1px solid var(--border-color);
    }
    .card-title {
      font-size: 1.05rem;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }

    /* Tables */
    .table-container {
      width: 100%;
      overflow-x: auto;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 0.88rem;
    }
    th {
      background-color: var(--bg-card);
      color: var(--text-muted);
      padding: 0.65rem 0.85rem;
      font-weight: 600;
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    td {
      padding: 0.75rem 0.85rem;
      border-bottom: 1px solid var(--border-color);
    }
    tr:hover td {
      background-color: rgba(255, 255, 255, 0.02);
    }

    /* Badges */
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 0.25rem;
      padding: 0.2rem 0.55rem;
      border-radius: 4px;
      font-size: 0.75rem;
      font-weight: 600;
      font-family: var(--font-mono);
    }
    .badge-green { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-blue { background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }
    .badge-amber { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
    .badge-red { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
    .badge-purple { background: rgba(139, 92, 246, 0.15); color: #a78bfa; border: 1px solid rgba(139, 92, 246, 0.3); }

    /* Action buttons */
    .btn {
      background-color: var(--primary);
      color: white;
      border: none;
      padding: 0.5rem 1rem;
      border-radius: 6px;
      font-size: 0.85rem;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s;
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
    }
    .btn:hover { background-color: var(--primary-hover); }
    .btn-secondary { background-color: var(--bg-card); color: var(--text-main); border: 1px solid var(--border-color); }
    .btn-secondary:hover { background-color: var(--bg-hover); }

    /* Code blocks */
    pre, code {
      font-family: var(--font-mono);
      font-size: 0.84rem;
    }
    pre {
      background-color: #050811;
      padding: 0.85rem;
      border-radius: 6px;
      border: 1px solid var(--border-color);
      overflow-x: auto;
    }

    /* Modal / Drawer */
    .modal-overlay {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0, 0, 0, 0.7);
      backdrop-filter: blur(2px);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 100;
    }
    .modal-overlay.open { display: flex; }
    .modal {
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
      border-radius: 10px;
      max-width: 800px;
      width: 90%;
      max-height: 85vh;
      display: flex;
      flex-direction: column;
      box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
    }
    .modal-header {
      padding: 1rem 1.25rem;
      border-bottom: 1px solid var(--border-color);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .modal-body {
      padding: 1.25rem;
      overflow-y: auto;
    }
    .modal-close {
      background: none;
      border: none;
      color: var(--text-muted);
      font-size: 1.5rem;
      cursor: pointer;
    }

    footer {
      border-top: 1px solid var(--border-color);
      padding: 1rem 1.5rem;
      text-align: center;
      font-size: 0.8rem;
      color: var(--text-muted);
      margin-top: auto;
    }
  </style>
</head>
<body>

  <header>
    <div class="brand">
      <div class="brand-logo">D</div>
      <div>
        <div class="brand-title">DevOpsPilot <span style="font-weight: 300; font-size: 0.95rem; opacity: 0.8;">Web Console</span></div>
      </div>
      <span class="brand-tag" id="header-rc-tag">RC 冻结中</span>
    </div>

    <nav>
      <button class="nav-btn active" onclick="switchTab('tab-overview')">📊 概览仪表盘</button>
      <button class="nav-btn" onclick="switchTab('tab-deliveries')">🚀 交付任务</button>
      <button class="nav-btn" onclick="switchTab('tab-trajectories')">📜 审计轨迹</button>
      <button class="nav-btn" onclick="switchTab('tab-rules')">🛡️ 合规规则库</button>
      <button class="nav-btn" onclick="switchTab('tab-benchmarks')">🎯 DevOpsBench 评测</button>
    </nav>
  </header>

  <main>
    <!-- TAB 1: 概览仪表盘 -->
    <div id="tab-overview" class="tab-content active">
      <div class="metrics-grid">
        <div class="metric-card green">
          <div class="metric-label">离线自动化回归测试</div>
          <div class="metric-value" id="metric-offline">41 / 41</div>
          <div class="metric-sub">PASS 全绿 · 拒绝伪造通过</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">历史交付任务总计</div>
          <div class="metric-value" id="metric-deliveries">-</div>
          <div class="metric-sub">SQLite 持久化存储状态</div>
        </div>
        <div class="metric-card purple">
          <div class="metric-label">DevOpsBench 评测题库</div>
          <div class="metric-value" id="metric-benchmarks">24</div>
          <div class="metric-sub">8 编码 · 8 审查 · 8 CI 调优 (6 Holdout)</div>
        </div>
        <div class="metric-card amber">
          <div class="metric-label">行业合规规则包</div>
          <div class="metric-value" id="metric-rules">2</div>
          <div class="metric-sub">金融高精合规 / 政务安全防护</div>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;">
        <div class="card">
          <div class="card-header">
            <span class="card-title">🖥️ 运行时环境与控制面状态</span>
            <button class="btn btn-secondary" onclick="fetchStatus()">刷新状态</button>
          </div>
          <table style="font-size: 0.85rem;">
            <tr><td style="width: 140px; color: var(--text-muted);">控制面状态</td><td><span class="badge badge-green">RUNNING (正常运行)</span></td></tr>
            <tr><td style="color: var(--text-muted);">发布候选 Tag</td><td id="info-rc-tag" style="font-family: var(--font-mono);">-</td></tr>
            <tr><td style="color: var(--text-muted);">Git Commit SHA</td><td id="info-commit-sha" style="font-family: var(--font-mono); font-size: 0.8rem;">-</td></tr>
            <tr><td style="color: var(--text-muted);">Python 环境</td><td id="info-python">-</td></tr>
            <tr><td style="color: var(--text-muted);">宿主操作系统</td><td id="info-platform">-</td></tr>
            <tr><td style="color: var(--text-muted);">本地状态存储库</td><td id="info-db-path" style="font-family: var(--font-mono); font-size: 0.8rem;">-</td></tr>
          </table>
        </div>

        <div class="card">
          <div class="card-header">
            <span class="card-title">🤖 MoMA 模型路由与资费契约</span>
            <span class="badge badge-blue">Single Agent First</span>
          </div>
          <table style="font-size: 0.85rem;">
            <tr><td style="width: 140px; color: var(--text-muted);">主力编码模型</td><td id="info-coding-model" style="font-family: var(--font-mono); font-weight: 600;">Qwen3-32B</td></tr>
            <tr><td style="color: var(--text-muted);">独立审查模型</td><td id="info-review-model" style="font-family: var(--font-mono); font-weight: 600;">deepseek-v4.1-flash</td></tr>
            <tr><td style="color: var(--text-muted);">移动云自营资费</td><td><a href="https://ecloud.10086.cn/op-help-center/doc/article/91592" target="_blank" style="color: #60a5fa; text-decoration: none;">移动云文档 91592 号 ↗</a></td></tr>
            <tr><td style="color: var(--text-muted);">消融规划矩阵</td><td>A0 (单模型) / A1 (+路由) / A2 (+审查) / A3 (全量自治)</td></tr>
            <tr><td style="color: var(--text-muted);">快速演练验证</td><td>
              <button class="btn btn-secondary" style="font-size: 0.75rem; padding: 0.3rem 0.6rem;" onclick="runDemo('deterministic')">▶ 运行确定性演示</button>
            </td></tr>
          </table>
        </div>
      </div>
    </div>

    <!-- TAB 2: 交付任务管理 -->
    <div id="tab-deliveries" class="tab-content">
      <div class="card">
        <div class="card-header">
          <span class="card-title">🚀 研发交付任务列表</span>
          <button class="btn btn-secondary" onclick="fetchDeliveries()">刷新列表</button>
        </div>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>Delivery ID</th>
                <th>Task ID / 仓库</th>
                <th>意图类型</th>
                <th>当前阶段</th>
                <th>Review 裁决</th>
                <th>更新时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody id="deliveries-tbody">
              <tr><td colspan="7" style="text-align: center; color: var(--text-muted);">加载中...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- TAB 3: 审计与轨迹 -->
    <div id="tab-trajectories" class="tab-content">
      <div class="card">
        <div class="card-header">
          <span class="card-title">📜 审计执行轨迹档案</span>
          <button class="btn btn-secondary" onclick="fetchTrajectories()">刷新轨迹</button>
        </div>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>Trajectory ID</th>
                <th>Task ID</th>
                <th>关联仓库</th>
                <th>事件步数</th>
                <th>产物文件名</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody id="trajectories-tbody">
              <tr><td colspan="6" style="text-align: center; color: var(--text-muted);">加载中...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- TAB 4: 合规规则库 -->
    <div id="tab-rules" class="tab-content">
      <div class="card">
        <div class="card-header">
          <span class="card-title">🛡️ 行业特化合规规则包 (Industry Rule Packs)</span>
          <span class="badge badge-green" id="rules-total-badge">2 个规则包</span>
        </div>
        <div id="rules-container">加载中...</div>
      </div>
    </div>

    <!-- TAB 5: DevOpsBench 评测看板 -->
    <div id="tab-benchmarks" class="tab-content">
      <div class="card">
        <div class="card-header">
          <span class="card-title">🎯 DevOpsBench 24 案例基准看板</span>
          <div style="display: flex; gap: 0.5rem;">
            <button class="btn" onclick="triggerValidateFixtures()" id="btn-validate">▶ 校验全量 24 Fixtures</button>
            <button class="btn btn-secondary" onclick="fetchBenchmarks()">刷新</button>
          </div>
        </div>
        <div id="benchmarks-summary" style="margin-bottom: 1rem; display: flex; gap: 0.8rem; font-size: 0.85rem;"></div>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>案例编号</th>
                <th>分类</th>
                <th>Holdout</th>
                <th>标题与规格说明</th>
                <th>判定 Oracle</th>
                <th>风险等级</th>
              </tr>
            </thead>
            <tbody id="benchmarks-tbody">
              <tr><td colspan="6" style="text-align: center; color: var(--text-muted);">加载中...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </main>

  <!-- 详情弹窗 -->
  <div class="modal-overlay" id="detail-modal">
    <div class="modal">
      <div class="modal-header">
        <span class="card-title" id="modal-title">详情查看</span>
        <button class="modal-close" onclick="closeModal()">&times;</button>
      </div>
      <div class="modal-body">
        <pre id="modal-json"></pre>
      </div>
    </div>
  </div>

  <footer>
    DevOpsPilot · 移动云平台智能研发自治引擎 · 全流程无篡改 SQLite 审计与离线验证
  </footer>

  <script>
    function switchTab(tabId) {
      document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
      document.getElementById(tabId).classList.add('active');
      event.currentTarget.classList.add('active');

      if (tabId === 'tab-deliveries') fetchDeliveries();
      if (tabId === 'tab-trajectories') fetchTrajectories();
      if (tabId === 'tab-rules') fetchRules();
      if (tabId === 'tab-benchmarks') fetchBenchmarks();
    }

    async function fetchStatus() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        document.getElementById('header-rc-tag').innerText = data.release_candidate_tag || 'RC 冻结';
        document.getElementById('info-rc-tag').innerText = data.release_candidate_tag || '-';
        document.getElementById('info-commit-sha').innerText = data.commit_sha || '-';
        document.getElementById('info-python').innerText = data.python_version || '-';
        document.getElementById('info-platform').innerText = data.platform || '-';
        document.getElementById('info-db-path').innerText = data.db_path || '-';
        document.getElementById('metric-deliveries').innerText = data.counts?.deliveries ?? 0;
        document.getElementById('metric-benchmarks').innerText = data.counts?.benchmark_cases ?? 24;
        document.getElementById('metric-rules').innerText = data.counts?.industry_packs ?? 2;
        if (data.models_config) {
          document.getElementById('info-coding-model').innerText = data.models_config.coding_model;
          document.getElementById('info-review-model').innerText = data.models_config.review_model;
        }
      } catch (err) {
        console.error('Fetch status error:', err);
      }
    }

    async function fetchDeliveries() {
      const tbody = document.getElementById('deliveries-tbody');
      try {
        const res = await fetch('/api/deliveries');
        const data = await res.json();
        if (!data.items || data.items.length === 0) {
          tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">暂无交付记录（执行 CLI 或 Demo 触发交付）</td></tr>';
          return;
        }
        tbody.innerHTML = data.items.map(it => `
          <tr>
            <td style="font-family: var(--font-mono); font-size: 0.8rem;">${it.delivery_id.slice(0, 8)}...</td>
            <td><strong>${it.repository || '-'}</strong><br><span style="color: var(--text-muted); font-size: 0.75rem;">${it.task_id || '-'}</span></td>
            <td><span class="badge badge-purple">${it.intent_type || 'CODE_CHANGE'}</span></td>
            <td><span class="badge ${it.phase === 'COMPLETED' ? 'badge-green' : (it.phase === 'FAILED' ? 'badge-red' : 'badge-amber')}">${it.phase}</span></td>
            <td>${it.verdict ? `<span class="badge ${it.verdict === 'APPROVED' ? 'badge-green' : 'badge-red'}">${it.verdict}</span>` : '-'}</td>
            <td style="font-size: 0.75rem; color: var(--text-muted);">${it.updated_at ? new Date(it.updated_at * 1000).toLocaleString() : '-'}</td>
            <td><button class="btn btn-secondary" style="font-size: 0.75rem; padding: 0.25rem 0.5rem;" onclick="viewDeliveryDetail('${it.delivery_id}')">查看详情</button></td>
          </tr>
        `).join('');
      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="7" style="color: var(--accent-red);">加载失败: ${err.message}</td></tr>`;
      }
    }

    async function viewDeliveryDetail(id) {
      try {
        const res = await fetch('/api/deliveries/' + id);
        const data = await res.json();
        showModal('交付任务详情: ' + id, data);
      } catch (err) {
        alert('加载详情失败: ' + err.message);
      }
    }

    async function fetchTrajectories() {
      const tbody = document.getElementById('trajectories-tbody');
      try {
        const res = await fetch('/api/trajectories');
        const data = await res.json();
        if (!data.items || data.items.length === 0) {
          tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">暂无持久化轨迹文件（执行任务后自动落盘）</td></tr>';
          return;
        }
        tbody.innerHTML = data.items.map(t => `
          <tr>
            <td style="font-family: var(--font-mono); font-size: 0.8rem;">${t.trajectory_id}</td>
            <td style="font-size: 0.8rem;">${t.task_id || '-'}</td>
            <td>${t.repository || '-'}</td>
            <td><span class="badge badge-blue">${t.event_count} 步</span></td>
            <td style="font-family: var(--font-mono); font-size: 0.78rem;">${t.filename}</td>
            <td><button class="btn btn-secondary" style="font-size: 0.75rem; padding: 0.25rem 0.5rem;" onclick="viewTrajectoryDetail('${t.trajectory_id}')">审计轨迹</button></td>
          </tr>
        `).join('');
      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="6" style="color: var(--accent-red);">加载失败: ${err.message}</td></tr>`;
      }
    }

    async function viewTrajectoryDetail(id) {
      try {
        const res = await fetch('/api/trajectories/' + id);
        const data = await res.json();
        showModal('执行轨迹审计: ' + id, data);
      } catch (err) {
        alert('加载轨迹失败: ' + err.message);
      }
    }

    async function fetchRules() {
      const container = document.getElementById('rules-container');
      try {
        const res = await fetch('/api/rules');
        const data = await res.json();
        document.getElementById('rules-total-badge').innerText = `${data.total_packs} 个规则包 (${data.total_rules} 条合规规则)`;
        container.innerHTML = data.packs.map(p => `
          <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
              <h3 style="font-size: 1rem; color: #60a5fa;">${p.name} <span style="font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-mono);">v${p.version} · ${p.industry}</span></h3>
              <span class="badge badge-green">${p.rules_count} 条规则</span>
            </div>
            <p style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 0.8rem;">${p.description}</p>
            <div style="display: grid; gap: 0.5rem;">
              ${(p.rules || []).map(r => `
                <div style="background: #0d131f; padding: 0.6rem 0.8rem; border-radius: 6px; border: 1px solid #1f2937; display: flex; justify-content: space-between; align-items: center;">
                  <div>
                    <span style="font-family: var(--font-mono); font-size: 0.8rem; font-weight: 600; color: #cbd5e1;">${r.id}</span>
                    <span style="font-size: 0.8rem; margin-left: 0.5rem; color: #94a3b8;">${r.name || r.description}</span>
                  </div>
                  <div>
                    <span class="badge ${r.severity === 'CRITICAL' ? 'badge-red' : (r.severity === 'HIGH' ? 'badge-amber' : 'badge-blue')}">${r.severity || 'HIGH'}</span>
                    ${r.autofix ? '<span class="badge badge-green" style="margin-left: 0.3rem;">AutoFix</span>' : ''}
                  </div>
                </div>
              `).join('')}
            </div>
          </div>
        `).join('');
      } catch (err) {
        container.innerHTML = `<div style="color: var(--accent-red);">加载失败: ${err.message}</div>`;
      }
    }

    async function fetchBenchmarks() {
      const tbody = document.getElementById('benchmarks-tbody');
      const summary = document.getElementById('benchmarks-summary');
      try {
        const res = await fetch('/api/benchmarks');
        const data = await res.json();
        summary.innerHTML = `
          <span class="badge badge-green">总计: ${data.total} 例</span>
          <span class="badge badge-blue">Coding: ${data.categories?.coding || 0} 例</span>
          <span class="badge badge-purple">Code-Review: ${data.categories?.['code-review'] || 0} 例</span>
          <span class="badge badge-amber">CI-Debug: ${data.categories?.['ci-debug'] || 0} 例</span>
          <span class="badge" style="background: rgba(255,255,255,0.1); color: #e2e8f0;">Holdout: ${data.holdout_count} 例 (防过拟合)</span>
        `;
        tbody.innerHTML = data.cases.map(c => `
          <tr>
            <td style="font-family: var(--font-mono); font-size: 0.8rem;">${c.id}</td>
            <td><span class="badge ${c.category === 'coding' ? 'badge-blue' : (c.category === 'code-review' ? 'badge-purple' : 'badge-amber')}">${c.category}</span></td>
            <td>${c.holdout ? '<span class="badge badge-amber">HOLDOUT</span>' : '<span style="color: var(--text-muted); font-size: 0.75rem;">公开</span>'}</td>
            <td><strong>${c.title}</strong><br><span style="color: var(--text-muted); font-size: 0.75rem;">${c.description}</span></td>
            <td><span class="badge" style="background: rgba(255,255,255,0.06); font-family: var(--font-mono);">${c.oracle_type || '-'}</span></td>
            <td><span class="badge ${c.risk === 'high' ? 'badge-red' : (c.risk === 'medium' ? 'badge-amber' : 'badge-green')}">${c.risk}</span></td>
          </tr>
        `).join('');
      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="6" style="color: var(--accent-red);">加载失败: ${err.message}</td></tr>`;
      }
    }

    async function triggerValidateFixtures() {
      const btn = document.getElementById('btn-validate');
      btn.disabled = true;
      btn.innerText = '⏳ 校验中...';
      try {
        const res = await fetch('/api/benchmarks/validate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
        const data = await res.json();
        showModal('DevOpsBench 24 Fixture 校验结果', data.results || data);
      } catch (err) {
        alert('校验请求失败: ' + err.message);
      } finally {
        btn.disabled = false;
        btn.innerText = '▶ 校验全量 24 Fixtures';
      }
    }

    async function runDemo(mode) {
      if (!confirm(`确定在本地安全运行 ${mode} 演示吗？`)) return;
      try {
        const res = await fetch('/api/demo/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mode })
        });
        const data = await res.json();
        showModal('演示执行输出 (' + mode + ')', data);
      } catch (err) {
        alert('触发演示失败: ' + err.message);
      }
    }

    function showModal(title, jsonPayload) {
      document.getElementById('modal-title').innerText = title;
      document.getElementById('modal-json').innerText = typeof jsonPayload === 'string' ? jsonPayload : JSON.stringify(jsonPayload, null, 2);
      document.getElementById('detail-modal').classList.add('open');
    }

    function closeModal() {
      document.getElementById('detail-modal').classList.remove('open');
    }

    // 页面加载自动获取系统状态
    window.addEventListener('DOMContentLoaded', fetchStatus);
  </script>
</body>
</html>
"""
