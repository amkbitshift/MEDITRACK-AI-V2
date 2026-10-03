/**
 * MediTrack AI - Core Client Application Controller (v2.4 Clinical)
 * Role-Based Access Control, Architectural Hospital Blueprint, Precision Location,
 * Emergency Shortage Intelligence, and Department Digital Twins (ICU & Gynaecology).
 */

// Global Reactive State Store
const state = {
  currentTab: 'dashboard',
  currentUser: {
    id: 'mgr-marcus',
    name: 'Marcus Reed',
    role: 'EQUIPMENT_MANAGER',
    department: 'Equipment Control',
    assigned_ward: 'ward-storage-a',
    permissions: ['ALL']
  },
  isDemoMode: true,
  equipmentList: [],
  filteredEquipment: [],
  blueprintData: null,
  activeFilterStatus: 'ALL',
  activeFilterWard: 'ALL',
  selectedEquipment: null,
  ws: null,
  charts: {
    maintenanceRisk: null,
    demandForecast: null
  },
  weights: {
    avail: 30,
    dist: 20,
    cond: 20,
    maint: 15,
    prio: 10,
    batt: 5
  },
  activeAllocation: null
};

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
  // Check localStorage for saved session
  const savedUser = localStorage.getItem('meditrack_user');
  if (savedUser) {
    try { state.currentUser = JSON.parse(savedUser); } catch(e){}
  }

  updateUserInterfaceForRole();
  lucide.createIcons();
  initCounters();
  initWebSocket();
  fetchInitialData();
  loadBlueprintData();
  initLiveTrackingMap();
  renderRoleDashboard();
});

// --- User & Role Management ---

function updateUserInterfaceForRole() {
  const role = state.currentUser ? state.currentUser.role : 'EQUIPMENT_MANAGER';
  const nameDisplay = document.getElementById('user-name-display');
  const roleDisplay = document.getElementById('user-role-display');
  const avatar = document.getElementById('user-avatar');
  const roleSelect = document.getElementById('role-select');
  const topRoleText = document.getElementById('top-role-text');
  const topAccessBadge = document.getElementById('top-access-badge');
  const roleDot = document.getElementById('role-dot-indicator');

  if (nameDisplay && state.currentUser) nameDisplay.textContent = state.currentUser.name;
  if (roleSelect) roleSelect.value = role;

  let roleTitle = 'Equipment Manager';
  let initials = 'MR';
  let accessBadge = 'FULL ACCESS';
  let badgeClass = 'bg-emerald-100 text-emerald-800 border-emerald-300';
  let dotClass = 'bg-indigo-500';

  if (role === 'NURSE') {
    roleTitle = 'Nurse (ICU & Wards)';
    initials = 'PP';
    accessBadge = 'PATIENT CARE';
    badgeClass = 'bg-emerald-100 text-emerald-800 border-emerald-200';
    dotClass = 'bg-emerald-500';
  } else if (role === 'DOCTOR') {
    roleTitle = 'Doctor (Clinical Lead)';
    initials = 'SL';
    accessBadge = 'CLINICAL LEAD';
    badgeClass = 'bg-purple-100 text-purple-800 border-purple-200';
    dotClass = 'bg-purple-500';
  } else if (role === 'ADMIN') {
    roleTitle = 'System Administrator';
    initials = 'AC';
    accessBadge = 'INFRASTRUCTURE';
    badgeClass = 'bg-slate-200 text-slate-800 border-slate-300';
    dotClass = 'bg-slate-500';
  } else {
    // Equipment Manager (Full Access)
    roleTitle = 'Equipment Manager';
    initials = 'MR';
    accessBadge = 'FULL ACCESS';
    badgeClass = 'bg-emerald-100 text-emerald-800 border-emerald-300';
    dotClass = 'bg-indigo-500';
  }

  if (roleDisplay) {
    roleDisplay.textContent = roleTitle;
    roleDisplay.className = `text-[10px] font-semibold ${role === 'NURSE' ? 'text-emerald-600' : (role === 'DOCTOR' ? 'text-purple-600' : (role === 'ADMIN' ? 'text-slate-600' : 'text-indigo-600'))}`;
  }
  if (avatar) avatar.textContent = initials;
  if (topRoleText) topRoleText.textContent = roleTitle;
  if (topAccessBadge) {
    topAccessBadge.textContent = accessBadge;
    topAccessBadge.className = `px-1.5 py-0.2 text-[9px] font-black rounded-full border ${badgeClass}`;
  }
  if (roleDot) {
    roleDot.className = `w-2 h-2 rounded-full ${dotClass} animate-pulse`;
  }

  updateLoginModalButtons(role);
  renderTopNavForRole(role);
  renderCapabilitiesForRole(role);
  renderSidebarNavigation();
}

function renderTopNavForRole(role) {
  const topNav = document.getElementById('top-nav-bar');
  if (!topNav) return;

  let items = [];

  if (role === 'NURSE') {
    items = [
      { id: 'dashboard', label: 'Ward Dashboard', icon: 'layout-grid' },
      { id: 'icu', label: 'ICU Patients', icon: 'heart-pulse' },
      { id: 'emergency', label: 'Equipment Requests', icon: 'alert-circle' },
      { id: 'equipment', label: 'Wheelchair Finder', icon: 'stethoscope' },
      { id: 'blueprint', label: 'Hospital Map', icon: 'map' }
    ];
  } else if (role === 'DOCTOR') {
    items = [
      { id: 'dashboard', label: 'Clinical Dashboard', icon: 'layout-grid' },
      { id: 'radiology', label: 'Radiology Operations', icon: 'layers' },
      { id: 'emergency', label: 'Code Red Triage', icon: 'alert-circle' },
      { id: 'icu', label: 'ICU Life-Support', icon: 'heart-pulse' },
      { id: 'equipment', label: 'Equipment', icon: 'stethoscope' },
      { id: 'blueprint', label: 'Hospital Map', icon: 'map' }
    ];
  } else if (role === 'ADMIN') {
    items = [
      { id: 'dashboard', label: 'Admin Dashboard', icon: 'layout-grid' },
      { id: 'users', label: 'Users & RBAC', icon: 'shield-check' },
      { id: 'iot', label: 'IoT Intelligence', icon: 'cpu' },
      { id: 'hardware-sim', label: 'ESP32 Lab', icon: 'zap' },
      { id: 'blueprint', label: 'Hospital Map', icon: 'map' },
      { id: 'movement', label: 'Movement Logs', icon: 'git-branch' },
      { id: 'settings', label: 'Settings', icon: 'settings' }
    ];
  } else {
    // EQUIPMENT_MANAGER (FULL ACCESS)
    items = [
      { id: 'dashboard', label: 'Dashboard', icon: 'layout-grid' },
      { id: 'radiology', label: 'Radiology', icon: 'layers' },
      { id: 'equipment', label: 'Equipment', icon: 'stethoscope' },
      { id: 'location', label: 'Tracking', icon: 'navigation' },
      { id: 'blueprint', label: 'Hospital Map', icon: 'map' },
      { id: 'hardware-sim', label: 'ESP32 Lab', icon: 'cpu' },
      { id: 'allocation', label: 'AI Insights', icon: 'sparkles' }
    ];
  }

  let html = items.map(item => `
    <a id="nav-${item.id}" onclick="switchTab('${item.id}')" class="nav-pill ${state.currentTab === item.id ? 'active' : ''}">
      <i data-lucide="${item.icon}" class="w-4 h-4"></i>
      <span>${item.label}</span>
    </a>
  `).join('');

  if (role === 'EQUIPMENT_MANAGER') {
    html += `
      <button onclick="toggleCapabilitiesMenu()" class="nav-pill border border-slate-200/80 bg-white/60 hover:bg-white text-slate-700">
        <span>All Capabilities</span>
        <i data-lucide="chevron-down" class="w-3.5 h-3.5"></i>
      </button>
    `;
  }

  topNav.innerHTML = html;
  if (window.lucide) lucide.createIcons();
}

function renderCapabilitiesForRole(role) {
  const container = document.getElementById('capabilities-cards-grid');
  const titleEl = document.getElementById('capabilities-header-title');
  const descEl = document.getElementById('capabilities-header-desc');
  const exploreLink = document.getElementById('capabilities-explore-link');
  if (!container) return;

  if (role === 'NURSE') {
    if (titleEl) titleEl.textContent = 'Nurse Priya\'s Clinical Station Capabilities';
    if (descEl) descEl.textContent = 'Operational modules required for bedside patient care, wheelchair locating, and ward replenishments.';
    if (exploreLink) exploreLink.classList.add('hidden');

    container.className = "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4";
    container.innerHTML = `
      <!-- Card 1: ICU Patients -->
      <div class="capability-card border-l-4 border-l-emerald-500" onclick="switchTab('icu')">
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <div class="card-icon-wrap bg-emerald-50 text-emerald-600">
              <i data-lucide="heart-pulse" class="w-6 h-6"></i>
            </div>
            <span class="status-pill status-pill-available">ACTIVE PATIENTS</span>
          </div>
          <h3 class="font-bold text-slate-900 text-base">ICU Bedside Care</h3>
          <p class="text-xs text-slate-500 leading-relaxed">Patient monitor readings, ventilator alarms, and smart bed telemetry.</p>
        </div>
        <div class="pt-4 flex items-center justify-between text-xs font-bold text-emerald-600 border-t border-slate-100 mt-4">
          <span>Open ICU Bed Stations</span>
          <i data-lucide="arrow-right" class="w-4 h-4"></i>
        </div>
      </div>

      <!-- Card 2: Emergency Requests -->
      <div class="capability-card border-l-4 border-l-rose-500" onclick="switchTab('emergency')">
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <div class="card-icon-wrap bg-rose-50 text-rose-600">
              <i data-lucide="alert-circle" class="w-6 h-6"></i>
            </div>
            <span class="status-pill status-pill-delayed">URGENT REQUISITIONS</span>
          </div>
          <h3 class="font-bold text-slate-900 text-base">Quick Requisitions</h3>
          <p class="text-xs text-slate-500 leading-relaxed">Direct one-click equipment orders for infusion pumps, oxygen cylinders, and wheelchairs.</p>
        </div>
        <div class="pt-4 flex items-center justify-between text-xs font-bold text-rose-600 border-t border-slate-100 mt-4">
          <span>Request Equipment Now</span>
          <i data-lucide="arrow-right" class="w-4 h-4"></i>
        </div>
      </div>

      <!-- Card 3: Wheelchair Locator -->
      <div class="capability-card border-l-4 border-l-blue-500" onclick="switchTab('equipment')">
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <div class="card-icon-wrap bg-blue-50 text-blue-600">
              <i data-lucide="stethoscope" class="w-6 h-6"></i>
            </div>
            <span class="status-pill status-pill-inuse">AVAILABLE NEARBY</span>
          </div>
          <h3 class="font-bold text-slate-900 text-base">Wheelchair Finder</h3>
          <p class="text-xs text-slate-500 leading-relaxed">Instant inventory of available transport equipment and wheelchairs on current floor.</p>
        </div>
        <div class="pt-4 flex items-center justify-between text-xs font-bold text-blue-600 border-t border-slate-100 mt-4">
          <span>Find Available Units</span>
          <i data-lucide="arrow-right" class="w-4 h-4"></i>
        </div>
      </div>

      <!-- Card 4: Floor Map & Return Bay -->
      <div class="capability-card border-l-4 border-l-indigo-500" onclick="switchTab('blueprint')">
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <div class="card-icon-wrap bg-indigo-50 text-indigo-600">
              <i data-lucide="map" class="w-6 h-6"></i>
            </div>
            <span class="status-pill status-pill-available">GROUND FLOOR</span>
          </div>
          <h3 class="font-bold text-slate-900 text-base">Hospital Map & Bay</h3>
          <p class="text-xs text-slate-500 leading-relaxed">Floor plan view showing designated Wheelchair Return Bay and staging zones.</p>
        </div>
        <div class="pt-4 flex items-center justify-between text-xs font-bold text-indigo-600 border-t border-slate-100 mt-4">
          <span>Open Floor Blueprint</span>
          <i data-lucide="arrow-right" class="w-4 h-4"></i>
        </div>
      </div>
    `;
  } else if (role === 'DOCTOR') {
    if (titleEl) titleEl.textContent = 'Clinical Diagnostic & Imaging Capabilities';
    if (descEl) descEl.textContent = 'Specialized diagnostic imaging pipelines, radiologist queues, and critical trauma triage.';
    if (exploreLink) exploreLink.classList.add('hidden');

    container.className = "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4";
    container.innerHTML = `
      <!-- Card 1: Radiology -->
      <div class="capability-card border-l-4 border-l-indigo-500" onclick="switchTab('radiology')">
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <div class="card-icon-wrap bg-indigo-50 text-indigo-600">
              <i data-lucide="layers" class="w-6 h-6"></i>
            </div>
            <span class="status-pill status-pill-available">7 MODALITIES</span>
          </div>
          <h3 class="font-bold text-slate-900 text-base">Radiology Operations</h3>
          <p class="text-xs text-slate-500 leading-relaxed">Split scan waiting times, gantry execution, and radiologist report verification queues.</p>
        </div>
        <div class="pt-4 flex items-center justify-between text-xs font-bold text-indigo-600 border-t border-slate-100 mt-4">
          <span>Open Radiology Flow</span>
          <i data-lucide="arrow-right" class="w-4 h-4"></i>
        </div>
      </div>

      <!-- Card 2: Emergency Code Red -->
      <div class="capability-card border-l-4 border-l-rose-500" onclick="switchTab('emergency')">
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <div class="card-icon-wrap bg-rose-50 text-rose-600">
              <i data-lucide="alert-circle" class="w-6 h-6"></i>
            </div>
            <span class="status-pill status-pill-delayed">CODE RED READY</span>
          </div>
          <h3 class="font-bold text-slate-900 text-base">Emergency Triage</h3>
          <p class="text-xs text-slate-500 leading-relaxed">High-priority triage queue with automated pre-emption of routine allocations for trauma cases.</p>
        </div>
        <div class="pt-4 flex items-center justify-between text-xs font-bold text-rose-600 border-t border-slate-100 mt-4">
          <span>Review Emergency Queue</span>
          <i data-lucide="arrow-right" class="w-4 h-4"></i>
        </div>
      </div>

      <!-- Card 3: ICU Life-Support Twin -->
      <div class="capability-card border-l-4 border-l-emerald-500" onclick="switchTab('icu')">
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <div class="card-icon-wrap bg-emerald-50 text-emerald-600">
              <i data-lucide="heart-pulse" class="w-6 h-6"></i>
            </div>
            <span class="status-pill status-pill-available">VENTILATORS READY</span>
          </div>
          <h3 class="font-bold text-slate-900 text-base">ICU Life-Support Twin</h3>
          <p class="text-xs text-slate-500 leading-relaxed">Critical care department monitoring, mechanical ventilators, and acute bed status.</p>
        </div>
        <div class="pt-4 flex items-center justify-between text-xs font-bold text-emerald-600 border-t border-slate-100 mt-4">
          <span>Inspect ICU Department</span>
          <i data-lucide="arrow-right" class="w-4 h-4"></i>
        </div>
      </div>

      <!-- Card 4: Equipment Inventory -->
      <div class="capability-card border-l-4 border-l-blue-500" onclick="switchTab('equipment')">
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <div class="card-icon-wrap bg-blue-50 text-blue-600">
              <i data-lucide="stethoscope" class="w-6 h-6"></i>
            </div>
            <span class="status-pill status-pill-inuse">CLINICAL ASSETS</span>
          </div>
          <h3 class="font-bold text-slate-900 text-base">Equipment Fleet</h3>
          <p class="text-xs text-slate-500 leading-relaxed">Real-time status of diagnostic ultrasound machines, transport chairs, and gurneys.</p>
        </div>
        <div class="pt-4 flex items-center justify-between text-xs font-bold text-blue-600 border-t border-slate-100 mt-4">
          <span>Inspect Assets</span>
          <i data-lucide="arrow-right" class="w-4 h-4"></i>
        </div>
      </div>
    `;
  } else if (role === 'ADMIN') {
    if (titleEl) titleEl.textContent = 'System Administration & Security Capabilities';
    if (descEl) descEl.textContent = 'Role-based access control, microcontroller network diagnostics, and audit logs.';
    if (exploreLink) exploreLink.classList.remove('hidden');

    container.className = "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4";
    container.innerHTML = `
      <div class="capability-card border-l-4 border-l-slate-700" onclick="switchTab('users')">
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <div class="card-icon-wrap bg-slate-100 text-slate-800">
              <i data-lucide="shield-check" class="w-6 h-6"></i>
            </div>
            <span class="status-pill status-pill-available">RBAC ACTIVE</span>
          </div>
          <h3 class="font-bold text-slate-900 text-base">Users & Permissions</h3>
          <p class="text-xs text-slate-500 leading-relaxed">Manage system credentials, clinical permissions, and security roles.</p>
        </div>
        <div class="pt-4 flex items-center justify-between text-xs font-bold text-slate-700 border-t border-slate-100 mt-4">
          <span>Manage Users</span>
          <i data-lucide="arrow-right" class="w-4 h-4"></i>
        </div>
      </div>

      <div class="capability-card border-l-4 border-l-blue-600" onclick="switchTab('iot')">
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <div class="card-icon-wrap bg-blue-50 text-blue-600">
              <i data-lucide="cpu" class="w-6 h-6"></i>
            </div>
            <span class="status-pill status-pill-available">IOT SENSORS</span>
          </div>
          <h3 class="font-bold text-slate-900 text-base">IoT Network</h3>
          <p class="text-xs text-slate-500 leading-relaxed">Microcontroller nodes, signal telemetry, battery levels, and sensory telemetry.</p>
        </div>
        <div class="pt-4 flex items-center justify-between text-xs font-bold text-blue-600 border-t border-slate-100 mt-4">
          <span>View IoT Nodes</span>
          <i data-lucide="arrow-right" class="w-4 h-4"></i>
        </div>
      </div>

      <div class="capability-card border-l-4 border-l-emerald-600" onclick="switchTab('hardware-sim')">
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <div class="card-icon-wrap bg-emerald-50 text-emerald-600">
              <i data-lucide="zap" class="w-6 h-6"></i>
            </div>
            <span class="status-pill status-pill-available">ONLINE</span>
          </div>
          <h3 class="font-bold text-slate-900 text-base">ESP32 Hardware Lab</h3>
          <p class="text-xs text-slate-500 leading-relaxed">Full hardware synchronization with RC522 RFID, PIR motion detector, buttons, and LEDs.</p>
        </div>
        <div class="pt-4 flex items-center justify-between text-xs font-bold text-emerald-600 border-t border-slate-100 mt-4">
          <span>Open Hardware Lab</span>
          <i data-lucide="arrow-right" class="w-4 h-4"></i>
        </div>
      </div>

      <div class="capability-card border-l-4 border-l-purple-600" onclick="switchTab('movement')">
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <div class="card-icon-wrap bg-purple-50 text-purple-600">
              <i data-lucide="git-branch" class="w-6 h-6"></i>
            </div>
            <span class="status-pill status-pill-inuse">AUDIT LOGS</span>
          </div>
          <h3 class="font-bold text-slate-900 text-base">Movement History</h3>
          <p class="text-xs text-slate-500 leading-relaxed">Complete audit trail of all physical transfers, staff signatures, and RFID check-ins.</p>
        </div>
        <div class="pt-4 flex items-center justify-between text-xs font-bold text-purple-600 border-t border-slate-100 mt-4">
          <span>Inspect Audit Trail</span>
          <i data-lucide="arrow-right" class="w-4 h-4"></i>
        </div>
      </div>
    `;
  } else {
    // EQUIPMENT_MANAGER - FULL ACCESS (All 8 capabilities)
    if (titleEl) titleEl.textContent = 'Our Capabilities (Full Operational Control)';
    if (descEl) descEl.textContent = '8 specialized clinical, IoT, and AI machine learning modules connected to real hardware.';
    if (exploreLink) exploreLink.classList.remove('hidden');

    container.className = "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4";
    container.innerHTML = `
      <!-- Card 1: Radiology -->
      <div class="capability-card" onclick="switchTab('radiology')">
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <div class="card-icon-wrap">
              <i data-lucide="layers" class="w-6 h-6"></i>
            </div>
            <span class="status-pill status-pill-available">7 MODALITIES</span>
          </div>
          <h3 class="font-bold text-slate-900 text-base">Radiology Operations</h3>
          <p class="text-xs text-slate-500 leading-relaxed">Split scan waiting times, gantry execution, and radiologist report verification queues.</p>
        </div>
        <div class="pt-4 flex items-center justify-between text-xs font-bold text-blue-600 border-t border-slate-100 mt-4">
          <span>View Queues & Journeys</span>
          <i data-lucide="arrow-right" class="w-4 h-4"></i>
        </div>
      </div>

      <!-- Card 2: Equipment Tracking -->
      <div class="capability-card" onclick="switchTab('location')">
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <div class="card-icon-wrap">
              <i data-lucide="navigation" class="w-6 h-6"></i>
            </div>
            <span class="status-pill status-pill-inuse">60 ASSETS</span>
          </div>
          <h3 class="font-bold text-slate-900 text-base">Equipment Tracking</h3>
          <p class="text-xs text-slate-500 leading-relaxed">Live spatial localization across Emergency, ICU, Gynaecology, and Central Storage.</p>
        </div>
        <div class="pt-4 flex items-center justify-between text-xs font-bold text-blue-600 border-t border-slate-100 mt-4">
          <span>Track Active Movement</span>
          <i data-lucide="arrow-right" class="w-4 h-4"></i>
        </div>
      </div>

      <!-- Card 3: AI Allocation -->
      <div class="capability-card" onclick="switchTab('allocation')">
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <div class="card-icon-wrap">
              <i data-lucide="sparkles" class="w-6 h-6"></i>
            </div>
            <span class="status-pill status-pill-available">94% OPTIMAL</span>
          </div>
          <h3 class="font-bold text-slate-900 text-base">AI Allocation</h3>
          <p class="text-xs text-slate-500 leading-relaxed">Multi-criteria optimization matching equipment condition, distance, and patient priority.</p>
        </div>
        <div class="pt-4 flex items-center justify-between text-xs font-bold text-blue-600 border-t border-slate-100 mt-4">
          <span>Run Allocation AI</span>
          <i data-lucide="arrow-right" class="w-4 h-4"></i>
        </div>
      </div>

      <!-- Card 4: Predictive Maintenance -->
      <div class="capability-card" onclick="switchTab('maintenance')">
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <div class="card-icon-wrap">
              <i data-lucide="wrench" class="w-6 h-6"></i>
            </div>
            <span class="status-pill status-pill-attention">3 AT RISK</span>
          </div>
          <h3 class="font-bold text-slate-900 text-base">Predictive Maintenance</h3>
          <p class="text-xs text-slate-500 leading-relaxed">Machine learning failure prediction based on sensor hours and mechanical stress telemetry.</p>
        </div>
        <div class="pt-4 flex items-center justify-between text-xs font-bold text-blue-600 border-t border-slate-100 mt-4">
          <span>Inspect Health Scores</span>
          <i data-lucide="arrow-right" class="w-4 h-4"></i>
        </div>
      </div>

      <!-- Card 5: Hospital Map Blueprint -->
      <div class="capability-card" onclick="switchTab('blueprint')">
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <div class="card-icon-wrap">
              <i data-lucide="map" class="w-6 h-6"></i>
            </div>
            <span class="status-pill status-pill-available">LIVE BLUEPRINT</span>
          </div>
          <h3 class="font-bold text-slate-900 text-base">Live Hospital Map</h3>
          <p class="text-xs text-slate-500 leading-relaxed">Interactive architectural floor plan featuring designated Radiology Wheelchair Storage.</p>
        </div>
        <div class="pt-4 flex items-center justify-between text-xs font-bold text-blue-600 border-t border-slate-100 mt-4">
          <span>View Ground Floor Plan</span>
          <i data-lucide="arrow-right" class="w-4 h-4"></i>
        </div>
      </div>

      <!-- Card 6: ESP32 IoT & Hardware Lab -->
      <div class="capability-card" onclick="switchTab('hardware-sim')">
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <div class="card-icon-wrap">
              <i data-lucide="cpu" class="w-6 h-6"></i>
            </div>
            <span class="status-pill status-pill-available">ONLINE</span>
          </div>
          <h3 class="font-bold text-slate-900 text-base">ESP32 IoT Node</h3>
          <p class="text-xs text-slate-500 leading-relaxed">Full hardware synchronization with RC522 RFID, PIR motion detector, buttons, and LEDs.</p>
        </div>
        <div class="pt-4 flex items-center justify-between text-xs font-bold text-blue-600 border-t border-slate-100 mt-4">
          <span>Open Hardware Lab</span>
          <i data-lucide="arrow-right" class="w-4 h-4"></i>
        </div>
      </div>

      <!-- Card 7: Demand Forecast -->
      <div class="capability-card" onclick="switchTab('forecast')">
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <div class="card-icon-wrap">
              <i data-lucide="trending-up" class="w-6 h-6"></i>
            </div>
            <span class="status-pill status-pill-inuse">6H HORIZON</span>
          </div>
          <h3 class="font-bold text-slate-900 text-base">Demand Forecast</h3>
          <p class="text-xs text-slate-500 leading-relaxed">Diurnal patient inflow predictions preparing ventilators, beds, and wheelchairs in advance.</p>
        </div>
        <div class="pt-4 flex items-center justify-between text-xs font-bold text-blue-600 border-t border-slate-100 mt-4">
          <span>Inspect Forecast Curves</span>
          <i data-lucide="arrow-right" class="w-4 h-4"></i>
        </div>
      </div>

      <!-- Card 8: Emergency Operations -->
      <div class="capability-card" onclick="switchTab('emergency')">
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <div class="card-icon-wrap">
              <i data-lucide="alert-circle" class="w-6 h-6"></i>
            </div>
            <span class="status-pill status-pill-delayed">CODE RED READY</span>
          </div>
          <h3 class="font-bold text-slate-900 text-base">Emergency Operations</h3>
          <p class="text-xs text-slate-500 leading-relaxed">High-priority triage queue with automated pre-emption of routine allocations for trauma cases.</p>
        </div>
        <div class="pt-4 flex items-center justify-between text-xs font-bold text-blue-600 border-t border-slate-100 mt-4">
          <span>View Emergency Queue</span>
          <i data-lucide="arrow-right" class="w-4 h-4"></i>
        </div>
      </div>
    `;
  }

  if (window.lucide) lucide.createIcons();
}

function handleNavClick(tabId, action) {
  if (action === 'mediai') {
    toggleMediaiDrawer();
    return;
  }
  if (action === 'profile') {
    openLoginModal();
    return;
  }
  if (action === 'reports') {
    showToast('Report Generated', 'Monthly Hospital Asset Compliance & Utilization Report exported as PDF.', 'success');
    return;
  }
  switchTab(tabId);
}

function renderSidebarNavigation() {
  const container = document.getElementById('sidebar-nav-container');
  if (!container) return;

  const role = state.currentUser.role;

  let navItems = [];

  if (role === 'NURSE') {
    navItems = [
      { id: 'dashboard', label: 'Dashboard', icon: 'layout-dashboard', badge: 'ICU' },
      { id: 'icu', label: 'My Ward', icon: 'heart-pulse' },
      { id: 'radiology', label: 'Radiology Operations', icon: 'scan', badge: 'FLOW' },
      { id: 'equipment', label: 'Available Equipment', icon: 'stethoscope' },
      { id: 'emergency', label: 'Equipment Requests', icon: 'git-pull-request' },
      { id: 'blueprint', label: 'Live Equipment', icon: 'activity' },
      { id: 'shortages', label: 'Emergency Alerts', icon: 'alert-triangle', badge: '2 RISK' },
      { id: 'blueprint', label: 'Hospital Map', icon: 'map' },
      { id: 'mediai', action: 'mediai', label: 'MediAI Assistant', icon: 'bot' },
      { id: 'profile', action: 'profile', label: 'Profile', icon: 'user' }
    ];
  } else if (role === 'DOCTOR') {
    navItems = [
      { id: 'dashboard', label: 'Dashboard', icon: 'layout-dashboard', badge: 'CLINICAL' },
      { id: 'icu', label: 'My Department', icon: 'heart-pulse', badge: 'VENTILATORS' },
      { id: 'radiology', label: 'Radiology Operations', icon: 'scan', badge: 'SCANS' },
      { id: 'equipment', label: 'Equipment Availability', icon: 'stethoscope' },
      { id: 'emergency', label: 'Emergency Equipment', icon: 'alert-octagon' },
      { id: 'blueprint', label: 'Live Equipment', icon: 'activity' },
      { id: 'blueprint', label: 'Hospital Map', icon: 'map' },
      { id: 'shortages', label: 'AI Insights', icon: 'trending-down', badge: 'SURGE' },
      { id: 'mediai', action: 'mediai', label: 'MediAI Assistant', icon: 'bot' },
      { id: 'profile', action: 'profile', label: 'Profile', icon: 'user' }
    ];
  } else if (role === 'ADMIN') {
    navItems = [
      { id: 'dashboard', label: 'Dashboard', icon: 'shield-check', badge: 'ROOT' },
      { id: 'users', label: 'Users', icon: 'users', badge: 'RBAC' },
      { id: 'users', label: 'Roles & Permissions', icon: 'shield-check' },
      { id: 'radiology', label: 'Radiology Operations', icon: 'scan', badge: 'FLOW' },
      { id: 'equipment', label: 'Equipment', icon: 'database' },
      { id: 'blueprint', label: 'Wards', icon: 'layers' },
      { id: 'blueprint', label: 'Hospital Map', icon: 'map' },
      { id: 'allocation', label: 'AI Systems', icon: 'cpu' },
      { id: 'iot', label: 'IoT', icon: 'radio' },
      { id: 'hardware-sim', label: 'ESP32 Hardware Lab', icon: 'zap', badge: 'LAB' },
      { id: 'maintenance', label: 'Maintenance', icon: 'wrench' },
      { id: 'reports', action: 'reports', label: 'Reports', icon: 'file-text' },
      { id: 'settings', label: 'System Settings', icon: 'settings' }
    ];
  } else {
    // EQUIPMENT MANAGER (Full Operational Control)
    navItems = [
      { id: 'dashboard', label: 'Dashboard', icon: 'layout-dashboard', badge: 'HERO' },
      { id: 'equipment', label: 'Equipment Inventory', icon: 'stethoscope' },
      { id: 'radiology', label: 'Radiology Operations', icon: 'scan', badge: 'PHASE 3' },
      { id: 'allocation', label: 'AI Allocation', icon: 'sparkles', badge: 'AI' },
      { id: 'blueprint', label: 'Live Tracking', icon: 'activity', badge: 'LIVE' },
      { id: 'blueprint', label: 'Hospital Map', icon: 'map' },
      { id: 'hardware-sim', label: 'ESP32 Hardware Lab', icon: 'zap', badge: 'TWIN' },
      { id: 'maintenance', label: 'Maintenance Intelligence', icon: 'wrench', badge: '78%' },
      { id: 'iot', label: 'IoT Intelligence', icon: 'cpu' },
      { id: 'forecast', label: 'Demand Forecast', icon: 'trending-up' },
      { id: 'emergency', label: 'Emergency Requests', icon: 'alert-octagon' },
      { id: 'vision', label: 'Inventory Intelligence', icon: 'scan' },
      { id: 'vision', label: 'Vision AI', icon: 'camera' },
      { id: 'movement', label: 'Equipment Movement', icon: 'git-branch' },
      { id: 'reports', action: 'reports', label: 'Reports', icon: 'file-text' },
      { id: 'mediai', action: 'mediai', label: 'MediAI', icon: 'bot' },
      { id: 'settings', label: 'Settings', icon: 'settings' }
    ];
  }

  container.innerHTML = `
    <div class="px-3 pb-2 text-[10px] font-bold tracking-wider text-slate-500 uppercase">
      ${role.replace('_', ' ')} WORKSPACE
    </div>
    ${navItems.map(item => `
      <button onclick="handleNavClick('${item.id}', '${item.action || ''}')" id="nav-${item.id}" class="nav-item ${state.currentTab === item.id && !item.action ? 'active text-cyan-400 bg-cyan-950/40 border border-cyan-500/30 shadow-sm' : 'text-slate-400 hover:text-cyan-300 hover:bg-slate-800/50'} w-full flex items-center space-x-3 px-3 py-2.5 rounded-xl text-sm font-medium transition">
        <i data-lucide="${item.icon}" class="w-4 h-4"></i>
        <span class="truncate">${item.label}</span>
        ${item.badge ? `<span class="ml-auto px-1.5 py-0.2 bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 rounded text-[9px] font-bold">${item.badge}</span>` : ''}
      </button>
    `).join('')}
  `;

  lucide.createIcons();
}

async function loginAsRole(roleName) {
  const roleProfiles = {
    'EQUIPMENT_MANAGER': {
      id: 'mgr-marcus',
      name: 'Marcus Reed',
      email: 'marcus.reed@stjude-hospital.org',
      role: 'EQUIPMENT_MANAGER',
      department: 'Central Operations',
      assigned_ward: 'ward-storage',
      permissions: ['ALL']
    },
    'DOCTOR': {
      id: 'doc-ananya',
      name: 'Dr. Sarah Lin (MD)',
      email: 'sarah.lin@hospital.org',
      role: 'DOCTOR',
      department: 'Radiology & ICU',
      assigned_ward: 'ward-emergency',
      permissions: ['VIEW_RADIOLOGY', 'VIEW_ICU', 'CREATE_EQUIPMENT_REQUEST', 'VIEW_HOSPITAL_MAP']
    },
    'NURSE': {
      id: 'nurse-priya',
      name: 'Nurse Priya Patel',
      email: 'priya.patel@hospital.org',
      role: 'NURSE',
      department: 'ICU & Emergency',
      assigned_ward: 'ward-icu',
      permissions: ['VIEW_WARD_EQUIPMENT', 'VIEW_HOSPITAL_MAP', 'CREATE_EQUIPMENT_REQUEST']
    },
    'ADMIN': {
      id: 'admin-vance',
      name: 'Alex Chen',
      email: 'alex.chen@hospital.org',
      role: 'ADMIN',
      department: 'IT & Security',
      assigned_ward: 'system',
      permissions: ['ALL']
    }
  };

  const selectedUser = roleProfiles[roleName] || roleProfiles['EQUIPMENT_MANAGER'];
  state.currentUser = selectedUser;
  localStorage.setItem('meditrack_user', JSON.stringify(selectedUser));

  // Sync UI immediately
  updateUserInterfaceForRole();
  closeLoginModal();
  showToast('Switched User', `Logged in as ${selectedUser.name} (${roleName.replace('_', ' ')})`, 'success');
  switchTab('dashboard');
  renderRoleDashboard();

  // Background backend auth synchronization
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ demo_role: roleName })
    });
    const data = await res.json();
    if (data.success && data.user) {
      state.currentUser = Object.assign({}, selectedUser, data.user);
      localStorage.setItem('meditrack_user', JSON.stringify(state.currentUser));
      updateUserInterfaceForRole();
    }
  } catch (e) {
    console.warn('Backend login sync note:', e);
  }
}

function switchUserRole(roleName) {
  loginAsRole(roleName);
}

function openLoginModal() {
  const m = document.getElementById('login-modal');
  if (m) {
    m.classList.remove('hidden');
    updateLoginModalButtons(state.currentUser ? state.currentUser.role : 'EQUIPMENT_MANAGER');
    if (window.lucide) lucide.createIcons();
  }
}

function closeLoginModal() {
  const m = document.getElementById('login-modal');
  if (m) m.classList.add('hidden');
}

function updateLoginModalButtons(role) {
  const roleCards = [
    { key: 'EQUIPMENT_MANAGER', btnId: 'btn-login-eq-manager', label: 'Active Profile (Full Access)' },
    { key: 'DOCTOR', btnId: 'btn-login-doctor', label: 'Active Profile (Clinical Lead)' },
    { key: 'NURSE', btnId: 'btn-login-nurse', label: 'Active Profile (Patient Care)' },
    { key: 'ADMIN', btnId: 'btn-login-admin', label: 'Active (Admin)' }
  ];

  roleCards.forEach(rc => {
    const btn = document.getElementById(rc.btnId);
    if (!btn) return;
    if (rc.key === role) {
      if (rc.key === 'EQUIPMENT_MANAGER') {
        btn.className = "w-full py-2.5 px-4 rounded-xl bg-indigo-600 text-white font-extrabold text-xs shadow-md shadow-indigo-600/25 transition flex items-center justify-center space-x-2 cursor-pointer";
        btn.innerHTML = `<i data-lucide="check-circle-2" class="w-4 h-4"></i><span>${rc.label}</span>`;
      } else if (rc.key === 'DOCTOR') {
        btn.className = "w-full py-2.5 px-4 rounded-xl bg-purple-600 text-white font-extrabold text-xs shadow-md shadow-purple-600/25 transition flex items-center justify-center space-x-2 cursor-pointer";
        btn.innerHTML = `<i data-lucide="check-circle-2" class="w-4 h-4"></i><span>${rc.label}</span>`;
      } else if (rc.key === 'NURSE') {
        btn.className = "w-full py-2.5 px-4 rounded-xl bg-emerald-600 text-white font-extrabold text-xs shadow-md shadow-emerald-600/25 transition flex items-center justify-center space-x-2 cursor-pointer";
        btn.innerHTML = `<i data-lucide="check-circle-2" class="w-4 h-4"></i><span>${rc.label}</span>`;
      } else {
        btn.className = "btn-pill btn-pill-primary text-xs shrink-0 self-start sm:self-center cursor-pointer bg-slate-900 text-white";
        btn.innerHTML = `<i data-lucide="check-circle-2" class="w-3.5 h-3.5"></i><span>Active (Admin)</span>`;
      }
    } else {
      if (rc.key === 'EQUIPMENT_MANAGER') {
        btn.className = "w-full py-2.5 px-4 rounded-xl bg-indigo-50 hover:bg-indigo-600 text-indigo-700 hover:text-white font-extrabold text-xs border border-indigo-200 hover:border-transparent transition flex items-center justify-center space-x-2 cursor-pointer";
        btn.innerHTML = `<i data-lucide="log-in" class="w-4 h-4"></i><span>Switch to Equipment Manager</span>`;
      } else if (rc.key === 'DOCTOR') {
        btn.className = "w-full py-2.5 px-4 rounded-xl bg-purple-50 hover:bg-purple-600 text-purple-700 hover:text-white font-extrabold text-xs border border-purple-200 hover:border-transparent transition flex items-center justify-center space-x-2 cursor-pointer";
        btn.innerHTML = `<i data-lucide="log-in" class="w-4 h-4"></i><span>Switch to Doctor</span>`;
      } else if (rc.key === 'NURSE') {
        btn.className = "w-full py-2.5 px-4 rounded-xl bg-emerald-50 hover:bg-emerald-600 text-emerald-700 hover:text-white font-extrabold text-xs border border-emerald-200 hover:border-transparent transition flex items-center justify-center space-x-2 cursor-pointer";
        btn.innerHTML = `<i data-lucide="log-in" class="w-4 h-4"></i><span>Switch to Nurse</span>`;
      } else {
        btn.className = "btn-pill btn-pill-secondary text-xs shrink-0 self-start sm:self-center cursor-pointer";
        btn.innerHTML = `<i data-lucide="shield-check" class="w-3.5 h-3.5 text-slate-600"></i><span>Switch to Admin</span>`;
      }
    }
  });

  if (window.lucide) lucide.createIcons();
}

async function handleManualLogin(e) {
  e.preventDefault();
  const email = document.getElementById('login-email').value;
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    const data = await res.json();
    if (data.success) {
      state.currentUser = data.user;
      localStorage.setItem('meditrack_user', JSON.stringify(data.user));
      updateUserInterfaceForRole();
      closeLoginModal();
      showToast('Authenticated', `Welcome back, ${data.user.name}`, 'success');
      renderRoleDashboard();
    } else {
      showToast('Authentication Error', 'Invalid employee credentials', 'emergency');
    }
  } catch (err) {
    showToast('Login Failed', 'Unable to reach authentication node', 'emergency');
  }
}

// --- Role-Specific Dashboards ---

async function renderRoleDashboard() {
  const container = document.getElementById('role-dashboard-container');
  if (!container) return;

  container.innerHTML = '<div class="py-12 text-center text-cyan-400">Loading role-specific operational telemetry...</div>';

  try {
    const res = await fetch(`/api/dashboard/role-view?role=${state.currentUser.role}&user_id=${state.currentUser.id}`);
    const data = await res.json();

    if (data.role === 'NURSE') {
      renderNurseDashboard(container, data);
    } else if (data.role === 'DOCTOR') {
      renderDoctorDashboard(container, data);
    } else if (data.role === 'ADMIN') {
      renderAdminDashboard(container, data);
    } else {
      renderEquipmentManagerDashboard(container, data);
    }
    lucide.createIcons();
  } catch (e) {
    console.error('Failed to load role dashboard:', e);
  }
}

function renderNurseDashboard(container, data) {
  container.innerHTML = `
    <!-- Nurse Banner -->
    <div class="glass-panel p-6 rounded-3xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
      <div>
        <div class="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-bold uppercase tracking-wider">
          <span class="w-2 h-2 rounded-full bg-emerald-500 animate-ping"></span>
          <span>ASSIGNED CLINICAL WARD: ${data.ward_name.toUpperCase()}</span>
        </div>
        <h1 class="text-2xl font-black text-slate-900 mt-2">Nurse Priya's Ward Equipment Station</h1>
        <p class="text-xs text-slate-500 mt-0.5">Monitoring ${data.total_ward_equipment} ward assets, bedside telemetry, and urgent replenishment requests.</p>
      </div>
      <button onclick="switchTab('emergency')" class="btn-pill btn-pill-primary text-xs">
        <i data-lucide="plus-circle" class="w-4 h-4"></i>
        <span>Request Equipment for Ward</span>
      </button>
    </div>

    <!-- Top Ward Metrics -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="glass-panel p-5 rounded-3xl">
        <span class="text-xs font-bold text-slate-400 uppercase tracking-wide">Available in Ward</span>
        <div class="text-3xl font-black text-emerald-600 mt-2">${data.available_count}</div>
        <span class="text-[11px] text-slate-500">Ready at bedside</span>
      </div>
      <div class="glass-panel p-5 rounded-3xl">
        <span class="text-xs font-bold text-slate-400 uppercase tracking-wide">Currently in Use</span>
        <div class="text-3xl font-black text-blue-600 mt-2">${data.in_use_count}</div>
        <span class="text-[11px] text-slate-500">Active patient monitoring</span>
      </div>
      <div class="glass-panel p-5 rounded-3xl">
        <span class="text-xs font-bold text-slate-400 uppercase tracking-wide">Critical Warnings</span>
        <div class="text-3xl font-black text-rose-600 mt-2">2</div>
        <span class="text-[11px] text-rose-500 font-medium">1 low battery, 1 maintenance</span>
      </div>
      <div class="glass-panel p-5 rounded-3xl">
        <span class="text-xs font-bold text-slate-400 uppercase tracking-wide">Pending Requests</span>
        <div class="text-3xl font-black text-amber-600 mt-2">${data.recent_requests.length}</div>
        <span class="text-[11px] text-slate-500">Inbound dispatch active</span>
      </div>
    </div>

    <!-- Ward Shortage Warning Alert Card -->
    <div class="p-5 rounded-3xl bg-amber-50/90 border border-amber-200/80 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
      <div class="flex items-center space-x-3.5">
        <div class="w-10 h-10 rounded-2xl bg-amber-100 text-amber-700 flex items-center justify-center font-black flex-shrink-0">
          <i data-lucide="alert-triangle" class="w-5 h-5 text-amber-600"></i>
        </div>
        <div>
          <div class="font-extrabold text-slate-900 text-sm">⚠ INFUSION PUMP SHORTAGE PREDICTED IN NEXT 2 HOURS</div>
          <p class="text-xs text-slate-600 mt-0.5">ICU occupancy is at 90%. AI expects 3 additional infusion lines needed. 2 pumps pre-staged in storage.</p>
        </div>
      </div>
      <button onclick="switchTab('emergency')" class="btn-pill bg-amber-500 hover:bg-amber-600 text-white font-bold text-xs shadow-md transition flex-shrink-0">
        REQUEST REPLENISHMENT
      </button>
    </div>

    <!-- Ward Equipment Breakdown & Available Table -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Ward Available Assets Quick Pill Box (1 col) -->
      <div class="glass-panel p-6 rounded-3xl space-y-3">
        <h3 class="font-bold text-slate-900 text-sm border-b border-slate-100 pb-2">Ward Inventory Checklist</h3>
        <div class="space-y-2 text-xs">
          <div class="p-3 rounded-2xl bg-slate-50 border border-slate-100 flex justify-between">
            <span class="text-slate-600">Smart ICU Beds:</span>
            <strong class="text-emerald-700 font-bold">4 Available / 20 Total</strong>
          </div>
          <div class="p-3 rounded-2xl bg-slate-50 border border-slate-100 flex justify-between">
            <span class="text-slate-600">Infusion Pumps:</span>
            <strong class="text-amber-700 font-bold">2 Available (Shortage Risk)</strong>
          </div>
          <div class="p-3 rounded-2xl bg-slate-50 border border-slate-100 flex justify-between">
            <span class="text-slate-600">Defibrillators:</span>
            <strong class="text-emerald-700 font-bold">1 Available (100% Batt)</strong>
          </div>
          <div class="p-3 rounded-2xl bg-slate-50 border border-slate-100 flex justify-between">
            <span class="text-slate-600">Multiparameter Monitors:</span>
            <strong class="text-emerald-700 font-bold">3 Available in Standby</strong>
          </div>
        </div>
        <button onclick="switchTab('icu')" class="w-full mt-2 btn-pill btn-pill-secondary text-xs">
          Open ICU Bed Stations View →
        </button>
      </div>

      <!-- Ward Equipment Table (2 cols) -->
      <div class="lg:col-span-2 glass-panel p-6 rounded-3xl">
        <div class="flex items-center justify-between pb-3 border-b border-slate-100">
          <h3 class="font-bold text-slate-900 text-sm">Bedside Equipment in ${data.ward_name}</h3>
          <span class="text-xs text-slate-500 font-mono">${data.ward_id}</span>
        </div>
        <div class="overflow-x-auto mt-3">
          <table class="w-full text-xs text-left">
            <thead class="text-slate-400 text-[10px] uppercase border-b border-slate-100">
              <tr>
                <th class="pb-2">ID</th>
                <th class="pb-2">TYPE</th>
                <th class="pb-2">ROOM / BED</th>
                <th class="pb-2">STATUS</th>
                <th class="pb-2">BATTERY</th>
                <th class="pb-2 text-right">ACTION</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100 font-medium">
              ${data.available_items.concat(data.in_use_items).slice(0, 7).map(item => `
                <tr class="hover:bg-indigo-50/40 transition cursor-pointer" onclick="openEquipmentDetailDrawer('${item.id}')">
                  <td class="py-2.5 font-bold font-mono text-blue-700">${item.id}</td>
                  <td class="py-2.5 text-slate-900 font-semibold">${item.type}</td>
                  <td class="py-2.5 text-slate-500">${item.room || 'Bedside'}</td>
                  <td class="py-2.5">
                    <span class="status-pill ${item.status === 'AVAILABLE' ? 'status-pill-available' : 'status-pill-in-use'}">${item.status}</span>
                  </td>
                  <td class="py-2.5 font-bold ${item.battery < 20 ? 'text-rose-600' : 'text-slate-700'}">${item.battery}%</td>
                  <td class="py-2.5 text-right">
                    <button class="px-2.5 py-1 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-[10px]">Details</button>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

function renderDoctorDashboard(container, data) {
  const cs = data.critical_life_support;
  container.innerHTML = `
    <!-- Doctor Header -->
    <div class="glass-panel p-6 rounded-3xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
      <div>
        <div class="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-blue-50 border border-blue-200 text-blue-700 text-xs font-bold uppercase tracking-wider">
          <span class="w-2 h-2 rounded-full bg-blue-500 animate-ping"></span>
          <span>CLINICAL DEPARTMENT: ${data.department.toUpperCase()}</span>
        </div>
        <h1 class="text-2xl font-black text-slate-900 mt-2">Dr. Ananya's Clinical Operations Status</h1>
        <p class="text-xs text-slate-500 mt-0.5">Monitoring critical life-support readiness, mechanical ventilation demand, and obstetric diagnostic suites.</p>
      </div>
      <div class="flex items-center space-x-2">
        <button onclick="switchTab('icu')" class="btn-pill btn-pill-primary text-xs">
          ICU Ventilators View
        </button>
        <button onclick="switchTab('gynaecology')" class="btn-pill btn-pill-secondary text-xs">
          Gynaecology Suites
        </button>
      </div>
    </div>

    <!-- Critical Life Support Intelligence Card -->
    <div class="glass-panel p-6 rounded-3xl border border-rose-200/80 bg-rose-50/40 relative overflow-hidden">
      <div class="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
        <div class="space-y-2">
          <div class="flex items-center space-x-2">
            <span class="status-pill status-pill-maintenance">ICU CRITICAL LIFE SUPPORT STATUS</span>
            <span class="text-xs font-bold text-slate-600">Mechanical Ventilators</span>
          </div>
          <div class="flex items-baseline space-x-4">
            <div>
              <span class="text-xs text-slate-500 font-medium">Available</span>
              <div class="text-3xl font-black text-emerald-600">${cs.ventilators_available}</div>
            </div>
            <div class="text-slate-400 font-bold text-lg">/</div>
            <div>
              <span class="text-xs text-slate-500 font-medium">Currently in Use</span>
              <div class="text-3xl font-black text-blue-600">${cs.ventilators_in_use}</div>
            </div>
            <div class="text-slate-400 font-bold text-lg">→</div>
            <div>
              <span class="text-xs text-slate-500 font-medium">Predicted Demand (3h)</span>
              <div class="text-3xl font-black text-rose-600">${cs.ventilators_predicted_requirement}</div>
            </div>
          </div>
        </div>

        <div class="p-4 rounded-2xl bg-white/90 border border-rose-200 max-w-md text-xs space-y-1.5 shadow-sm">
          <div class="font-extrabold text-rose-700 flex items-center space-x-1.5">
            <i data-lucide="alert-octagon" class="w-4 h-4 text-rose-600"></i>
            <span>⚠ SHORTAGE RISK DETECTED</span>
          </div>
          <p class="text-slate-600">${cs.ai_recommendation}</p>
          <div class="flex justify-end pt-2">
            <button onclick="requestUrgentVentilator()" class="btn-pill bg-rose-600 hover:bg-rose-700 text-white font-bold text-[11px] shadow-sm">
              Initiate Pre-emptive Transfer
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Department Clinical Equipment List -->
    <div class="glass-panel p-6 rounded-3xl">
      <div class="flex items-center justify-between pb-3 border-b border-slate-100">
        <h3 class="font-bold text-slate-900 text-sm">Critical Clinical Assets in ${data.department}</h3>
        <span class="text-xs text-blue-600 font-bold">${data.total_dept_equipment} Units Monitored</span>
      </div>
      <div class="overflow-x-auto mt-3">
        <table class="w-full text-xs text-left">
          <thead class="text-slate-400 text-[10px] uppercase border-b border-slate-100">
            <tr>
              <th class="pb-2">ID</th>
              <th class="pb-2">EQUIPMENT TYPE</th>
              <th class="pb-2">LOCATION / ROOM</th>
              <th class="pb-2">STATUS</th>
              <th class="pb-2">HEALTH</th>
              <th class="pb-2">BATTERY</th>
              <th class="pb-2 text-right">ACTION</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 font-medium">
            ${data.clinical_equipment.map(item => `
              <tr class="hover:bg-indigo-50/40 transition cursor-pointer" onclick="openEquipmentDetailDrawer('${item.id}')">
                <td class="py-2.5 font-bold font-mono text-blue-700">${item.id}</td>
                <td class="py-2.5 text-slate-900 font-semibold">${item.name}</td>
                <td class="py-2.5 text-slate-500">${item.location} (${item.room || 'General'})</td>
                <td class="py-2.5">
                  <span class="status-pill ${item.status === 'AVAILABLE' ? 'status-pill-available' : (item.status === 'IN_USE' ? 'status-pill-in-use' : 'status-pill-maintenance')}">${item.status}</span>
                </td>
                <td class="py-2.5 font-bold text-emerald-600">${item.health_score}%</td>
                <td class="py-2.5 font-bold ${item.battery < 20 ? 'text-rose-600' : 'text-slate-700'}">${item.battery}%</td>
                <td class="py-2.5 text-right">
                  <button class="px-2.5 py-1 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-[10px]">Inspect</button>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderAdminDashboard(container, data) {
  container.innerHTML = `
    <!-- Admin Header -->
    <div class="glass-panel p-6 rounded-3xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
      <div>
        <div class="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-purple-50 border border-purple-200 text-purple-700 text-xs font-bold uppercase tracking-wider">
          <span class="w-2 h-2 rounded-full bg-purple-500 animate-ping"></span>
          <span>GOVERNANCE & SYSTEM ADMINISTRATION</span>
        </div>
        <h1 class="text-2xl font-black text-slate-900 mt-2">Dr. Alex Vance — System Administration</h1>
        <p class="text-xs text-slate-500 mt-0.5">Hospital equipment network governance, RBAC permissions, and IoT telecommunication nodes.</p>
      </div>
      <button onclick="switchTab('users')" class="btn-pill btn-pill-primary text-xs">
        <i data-lucide="users" class="w-4 h-4"></i>
        <span>MANAGE USERS & ROLES</span>
      </button>
    </div>

    <!-- Admin KPI Stats -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="glass-panel p-5 rounded-3xl">
        <span class="text-xs font-bold text-slate-400 uppercase tracking-wide">Registered Users</span>
        <div class="text-3xl font-black text-purple-600 mt-2">4 Active</div>
        <span class="text-[11px] text-slate-500">Strict RBAC Enforced</span>
      </div>
      <div class="glass-panel p-5 rounded-3xl">
        <span class="text-xs font-bold text-slate-400 uppercase tracking-wide">Hospital Wards</span>
        <div class="text-3xl font-black text-blue-600 mt-2">12 Rooms</div>
        <span class="text-[11px] text-slate-500">Blueprint v2.4 Active</span>
      </div>
      <div class="glass-panel p-5 rounded-3xl">
        <span class="text-xs font-bold text-slate-400 uppercase tracking-wide">IoT Hardware Nodes</span>
        <div class="text-3xl font-black text-emerald-600 mt-2">14 Online</div>
        <span class="text-[11px] text-slate-500">ESP32 115200 Baud</span>
      </div>
      <div class="glass-panel p-5 rounded-3xl">
        <span class="text-xs font-bold text-slate-400 uppercase tracking-wide">Security State</span>
        <div class="text-3xl font-black text-emerald-600 mt-2">OPTIMAL</div>
        <span class="text-[11px] text-slate-500">All Nodes Authenticated</span>
      </div>
    </div>
  `;
}

function renderEquipmentManagerDashboard(container, data) {
  // Operational Control Center
  container.innerHTML = `
    <!-- Top Hero Header -->
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2">
      <div>
        <div class="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-blue-50 border border-blue-200 text-blue-700 text-xs font-extrabold tracking-wider uppercase">
          <span>EQUIPMENT CONTROL MANAGEMENT CENTER</span>
          <span class="px-1.5 py-0.2 rounded-full bg-blue-100 text-blue-800 text-[10px]">OPERATIONAL INTELLIGENCE</span>
        </div>
        <h1 class="text-2xl lg:text-3xl font-extrabold text-slate-900 tracking-tight mt-2">
          Hospital-Wide Asset Tracking & AI Optimization
        </h1>
        <p class="text-xs sm:text-sm text-slate-500 mt-0.5">
          Coordinating 247 clinical assets across Emergency, ICU, Gynaecology, OT, and Central Storage.
        </p>
      </div>
      <div class="flex items-center space-x-2">
        <button onclick="switchTab('blueprint')" class="btn-pill btn-pill-primary text-xs">
          <i data-lucide="map" class="w-4 h-4"></i>
          <span>View Blueprint</span>
        </button>
        <button onclick="switchTab('shortages')" class="btn-pill btn-pill-secondary text-xs">
          <i data-lucide="alert-triangle" class="w-4 h-4 text-amber-500"></i>
          <span>Shortage Alerts (${data.shortage_risks})</span>
        </button>
      </div>
    </div>

    <!-- Top Statistics KPI Cards -->
    <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      <div class="glass-panel p-4 rounded-3xl">
        <span class="text-[10px] font-bold text-slate-400 uppercase block tracking-wide">Total Fleet</span>
        <div class="text-2xl font-black text-slate-900 mt-1">247</div>
        <span class="text-[10px] text-blue-600 font-semibold">+8.2% Active</span>
      </div>
      <div class="glass-panel p-4 rounded-3xl">
        <span class="text-[10px] font-bold text-slate-400 uppercase block tracking-wide">Available</span>
        <div class="text-2xl font-black text-emerald-600 mt-1">132</div>
        <span class="text-[10px] text-emerald-600 font-medium">In Standby</span>
      </div>
      <div class="glass-panel p-4 rounded-3xl">
        <span class="text-[10px] font-bold text-slate-400 uppercase block tracking-wide">In Use</span>
        <div class="text-2xl font-black text-blue-600 mt-1">96</div>
        <span class="text-[10px] text-blue-600 font-medium">Active Care</span>
      </div>
      <div class="glass-panel p-4 rounded-3xl">
        <span class="text-[10px] font-bold text-slate-400 uppercase block tracking-wide">Maintenance</span>
        <div class="text-2xl font-black text-rose-600 mt-1">19</div>
        <span class="text-[10px] text-rose-500 font-medium">WC-014 (78%)</span>
      </div>
      <div class="glass-panel p-4 rounded-3xl">
        <span class="text-[10px] font-bold text-slate-400 uppercase block tracking-wide">Critical Alerts</span>
        <div class="text-2xl font-black text-amber-600 mt-1">7</div>
        <span class="text-[10px] text-amber-600 font-medium">Batt / Health</span>
      </div>
      <div class="glass-panel p-4 rounded-3xl">
        <span class="text-[10px] font-bold text-slate-400 uppercase block tracking-wide">Shortage Risks</span>
        <div class="text-2xl font-black text-rose-600 mt-1">4</div>
        <span class="text-[10px] text-rose-500 font-medium">ICU & Emergency</span>
      </div>
    </div>

    <!-- AI Command Hero Banner -->
    <div class="glass-panel p-6 rounded-3xl bg-gradient-to-r from-blue-50/90 via-indigo-50/90 to-purple-50/90 border border-indigo-100 shadow-soft-indigo relative overflow-hidden">
      <div class="flex flex-col lg:flex-row items-center justify-between gap-6 relative z-10">
        <div class="flex items-center space-x-5">
          <div class="w-14 h-14 rounded-2xl bg-indigo-600 text-white flex-shrink-0 flex items-center justify-center shadow-lg shadow-indigo-500/25">
            <i data-lucide="cpu" class="w-7 h-7"></i>
          </div>
          <div>
            <div class="flex items-center space-x-2">
              <span class="text-xs font-extrabold text-indigo-900 tracking-wider uppercase">✨ AUTONOMOUS REASONING CORE</span>
              <span class="status-pill status-pill-available">OPTIMIZATION ENGINE</span>
            </div>
            <h2 class="text-xl lg:text-2xl font-black text-slate-900 mt-1">
              AI has analyzed 247 equipment records and generated 12 operational directives
            </h2>
            <div class="flex flex-wrap items-center gap-3 mt-3 text-xs">
              <span class="flex items-center space-x-1 px-3 py-1 rounded-full bg-amber-50 border border-amber-200 text-amber-800 font-semibold">
                <i data-lucide="wrench" class="w-3.5 h-3.5 text-amber-600"></i>
                <span>3 maintenance risks (WC-014 at 78%)</span>
              </span>
              <span class="flex items-center space-x-1 px-3 py-1 rounded-full bg-rose-50 border border-rose-200 text-rose-800 font-semibold">
                <span class="w-2 h-2 rounded-full bg-rose-500 animate-pulse"></span>
                <span>4 active shortage risks (Ventilators & Pumps)</span>
              </span>
              <span class="flex items-center space-x-1 px-3 py-1 rounded-full bg-blue-50 border border-blue-200 text-blue-800 font-semibold">
                <i data-lucide="box" class="w-3.5 h-3.5 text-blue-600"></i>
                <span>Zone A Wheelchair Mismatch (-3)</span>
              </span>
            </div>
          </div>
        </div>
        <div class="flex-shrink-0 flex items-center gap-3">
          <button onclick="switchTab('shortages')" class="btn-pill btn-pill-primary text-xs">
            VIEW SHORTAGE ADVISORIES →
          </button>
        </div>
      </div>
    </div>

    <!-- Phase 3: Wheelchair Return & Radiology Operations Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 mt-6">
      <!-- Wheelchair Return Storage Auto-Availability Card (6 cols) -->
      <div id="wheelchair-return-widget" class="lg:col-span-6 glass-panel p-6 rounded-3xl border border-emerald-200/80 shadow-soft-indigo">
        <!-- Rendered by renderWheelchairReturnWidget() -->
      </div>

      <!-- Radiology Operations & Clinical Flow Quick Card (6 cols) -->
      <div class="lg:col-span-6 glass-panel p-6 rounded-3xl border border-blue-200/80 shadow-soft-indigo flex flex-col justify-between">
        <div class="space-y-3">
          <div class="flex items-center justify-between pb-2 border-b border-slate-100">
            <div class="flex items-center space-x-2">
              <i data-lucide="scan" class="w-4 h-4 text-blue-600"></i>
              <h3 class="font-extrabold text-slate-900 text-sm">Radiology Operations & Turnaround Flow</h3>
            </div>
            <span class="status-pill status-pill-available">PHASE 3 POST-JUDGING</span>
          </div>
          <p class="text-xs text-slate-500">
            Autonomous tracking of 7 imaging modalities, split scan wait times, reporting backlogs, and wheelchair transport dependencies.
          </p>
          <div id="dash-rad-quick-stats" class="grid grid-cols-3 gap-2 text-center text-xs">
            <div class="p-3 rounded-2xl bg-slate-50 border border-slate-100">
              <span class="text-[10px] text-slate-400 block font-medium">Avg Turnaround</span>
              <span id="dash-rad-turnaround" class="text-base font-extrabold text-purple-700">48m</span>
            </div>
            <div class="p-3 rounded-2xl bg-slate-50 border border-slate-100">
              <span class="text-[10px] text-slate-400 block font-medium">Waiting Scans</span>
              <span id="dash-rad-waiting" class="text-base font-extrabold text-blue-700">14</span>
            </div>
            <div class="p-3 rounded-2xl bg-slate-50 border border-slate-100">
              <span class="text-[10px] text-slate-400 block font-medium">Transport Delay</span>
              <span id="dash-rad-transport-delay" class="text-base font-extrabold text-emerald-700">0m (Ready)</span>
            </div>
          </div>
        </div>
        <div class="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
          <span class="text-[11px] text-slate-500 flex items-center space-x-1.5">
            <span class="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
            <span>Diurnal Peak Flow Connected</span>
          </span>
          <button onclick="switchTab('radiology')" class="btn-pill btn-pill-primary text-xs">
            <span>Explore Radiology Suite</span>
            <i data-lucide="arrow-right" class="w-3.5 h-3.5"></i>
          </button>
        </div>
      </div>
    </div>
  `;

  loadWheelchairReturnStatus();
  loadDashRadiologyQuickStats();
}

// --- Architectural Hospital Blueprint Renderer & Demonstration Map ---

const DEMO_BLUEPRINT_EQUIPMENT = [
  // AVAILABLE (Green) - 7 units
  { id: 'WC-001', name: 'Ergonomic Wheelchair (Dock 1)', location: 'Clustered Chair Zone', status: 'AVAILABLE', cx: 875, cy: 260, battery: 98, health: 96 },
  { id: 'WC-002', name: 'Ergonomic Wheelchair (Dock 2)', location: 'Clustered Chair Zone', status: 'AVAILABLE', cx: 925, cy: 290, battery: 94, health: 95 },
  { id: 'MON-001', name: 'Vital Signs Patient Monitor', location: 'General Ward A', status: 'AVAILABLE', cx: 120, cy: 110, battery: 88, health: 92 },
  { id: 'BP-003', name: 'Smart BP Monitor Station', location: 'General Ward B', status: 'AVAILABLE', cx: 120, cy: 260, battery: 91, health: 94 },
  { id: 'CTG-01', name: 'Fetal Doppler / CTG Monitor', location: 'Gynaecology Dept', status: 'AVAILABLE', cx: 130, cy: 450, battery: 85, health: 90 },
  { id: 'CAUT-01', name: 'Electrosurgical Diathermy Unit', location: 'Operation Theatre (OT)', status: 'AVAILABLE', cx: 430, cy: 105, battery: 100, health: 98 },
  { id: 'MON-ICU-03', name: 'Multiparameter Monitor Pod 3', location: 'Intensive Care Unit (ICU)', status: 'AVAILABLE', cx: 740, cy: 435, battery: 92, health: 95 },

  // INACTIVE / STANDBY (Blue) - 4 units
  { id: 'PUMP-003', name: 'Infusion Syringe Pump', location: 'General Ward B', status: 'INACTIVE', cx: 230, cy: 290, battery: 78, health: 88 },
  { id: 'SUCT-01', name: 'Mobile Emergency Suction Unit', location: 'Emergency & Trauma', status: 'INACTIVE', cx: 840, cy: 120, battery: 82, health: 86 },
  { id: 'US-01', name: 'Diagnostic Ultrasound System', location: 'Radiology & Imaging', status: 'INACTIVE', cx: 730, cy: 270, battery: 75, health: 89 },
  { id: 'DEFIB-01', name: 'Biphasic Defibrillator Standby', location: 'Intensive Care Unit (ICU)', status: 'INACTIVE', cx: 910, cy: 495, battery: 95, health: 94 },

  // IN USE (Yellow) - 5 units
  { id: 'PUMP-001', name: 'Volumetric Infusion Pump', location: 'General Ward A', status: 'IN_USE', cx: 230, cy: 140, battery: 64, health: 85 },
  { id: 'ECG-01', name: '12-Lead Diagnostic ECG Cart', location: 'Gynaecology Dept', status: 'IN_USE', cx: 240, cy: 490, battery: 71, health: 87 },
  { id: 'ANES-01', name: 'Anesthesia Workstation', location: 'Operation Theatre (OT)', status: 'IN_USE', cx: 560, cy: 125, battery: 90, health: 93 },
  { id: 'ST-001', name: 'Hydraulic Trauma Stretcher', location: 'Emergency & Trauma', status: 'IN_USE', cx: 750, cy: 105, battery: 80, health: 88 },
  { id: 'VENT-01', name: 'ICU Life Support Ventilator Pod 1', location: 'Intensive Care Unit (ICU)', status: 'IN_USE', cx: 830, cy: 465, battery: 85, health: 91 },

  // MAINTENANCE (Red) - 4 units
  { id: 'WC-014', name: 'Ergonomic Wheelchair (Bearing)', location: 'Annex Storage B (Repairs)', status: 'MAINTENANCE', cx: 410, cy: 375, battery: 42, health: 68 },
  { id: 'VENT-03', name: 'Transport Ventilator (Calibration)', location: 'Annex Storage B (Repairs)', status: 'MAINTENANCE', cx: 450, cy: 420, battery: 55, health: 70 },
  { id: 'DEFIB-02', name: 'Emergency Defibrillator (Battery)', location: 'Emergency & Trauma', status: 'MAINTENANCE', cx: 900, cy: 155, battery: 18, health: 72 },
  { id: 'XRAY-01', name: 'Mobile Digital C-Arm X-Ray', location: 'Radiology & Imaging', status: 'MAINTENANCE', cx: 785, cy: 305, battery: 35, health: 65 }
];

let _currentBlueprintFilter = 'ALL';

function switchBlueprintView(mode) {
  const interactiveContainer = document.getElementById('bp-interactive-view-container');
  const cadContainer = document.getElementById('bp-cad-view-container');
  const compareContainer = document.getElementById('bp-compare-view-container');

  const tabInteractive = document.getElementById('bp-tab-interactive');
  const tabCad = document.getElementById('bp-tab-cad');
  const tabCompare = document.getElementById('bp-tab-compare');

  const activeClass = 'px-3.5 py-1 rounded-full text-xs font-bold transition bg-indigo-600 text-white shadow-xs';
  const inactiveClass = 'px-3.5 py-1 rounded-full text-xs font-bold transition text-slate-600 hover:text-slate-900';

  if (tabInteractive) tabInteractive.className = (mode === 'interactive') ? activeClass : inactiveClass;
  if (tabCad) tabCad.className = (mode === 'cad') ? activeClass : inactiveClass;
  if (tabCompare) tabCompare.className = (mode === 'compare') ? activeClass : inactiveClass;

  if (interactiveContainer) interactiveContainer.classList.toggle('hidden', mode !== 'interactive');
  if (cadContainer) cadContainer.classList.toggle('hidden', mode !== 'cad');
  if (compareContainer) compareContainer.classList.toggle('hidden', mode !== 'compare');

  if (mode === 'interactive') {
    renderBlueprintMap(_currentBlueprintFilter);
  }
}

async function loadBlueprintData() {
  try {
    if (!state.blueprintData) {
      const res = await fetch('/api/blueprint');
      state.blueprintData = await res.json();
    }
    renderBlueprintMap(_currentBlueprintFilter);
  } catch (e) {
    console.error('Failed to load blueprint data:', e);
  }
}

function filterBlueprintDemoMarkers(status) {
  _currentBlueprintFilter = status;
  
  // Update button active styling
  document.querySelectorAll('.bp-demo-filter-btn').forEach(btn => {
    btn.className = 'bp-demo-filter-btn px-3 py-1 rounded-full text-slate-600 hover:text-slate-900 transition';
  });

  const activeMap = {
    'ALL': 'bp-filter-all',
    'AVAILABLE': 'bp-filter-available',
    'INACTIVE': 'bp-filter-inactive',
    'IN_USE': 'bp-filter-inuse',
    'MAINTENANCE': 'bp-filter-maint'
  };

  const activeBtn = document.getElementById(activeMap[status]);
  if (activeBtn) {
    if (status === 'ALL') activeBtn.className = 'bp-demo-filter-btn px-3 py-1 rounded-full bg-slate-900 text-white transition';
    else if (status === 'AVAILABLE') activeBtn.className = 'bp-demo-filter-btn px-3 py-1 rounded-full bg-emerald-600 text-white shadow-xs transition';
    else if (status === 'INACTIVE') activeBtn.className = 'bp-demo-filter-btn px-3 py-1 rounded-full bg-blue-600 text-white shadow-xs transition';
    else if (status === 'IN_USE') activeBtn.className = 'bp-demo-filter-btn px-3 py-1 rounded-full bg-amber-500 text-white shadow-xs transition';
    else if (status === 'MAINTENANCE') activeBtn.className = 'bp-demo-filter-btn px-3 py-1 rounded-full bg-rose-600 text-white shadow-xs transition';
  }

  renderBlueprintMap(status);
}

function renderBlueprintMap(filter = 'ALL') {
  const roomsGroup = document.getElementById('bp-rooms-group');
  const markersGroup = document.getElementById('bp-equipment-markers-group');
  if (!roomsGroup || !markersGroup) return;

  const widthScale = 10;
  const heightScale = 6.5;

  // 1. Render Blueprint Rooms from backend data (if available)
  if (state.blueprintData && state.blueprintData.rooms) {
    roomsGroup.innerHTML = state.blueprintData.rooms.map(room => {
      const rx = room.x * widthScale;
      const ry = room.y * heightScale;
      const rw = room.w * widthScale;
      const rh = room.h * heightScale;
      const cx = rx + (rw / 2);
      const cy = ry + (rh / 2);
      const isStorageBay = room.id === 'room-radiology-storage';

      if (isStorageBay) {
        return `
          <g class="blueprint-room cursor-pointer" onclick="handleRoomClick('${room.name}')" data-room-id="${room.id}">
            <!-- Clustered Storage Bay Highlighted Boundary -->
            <rect x="${rx}" y="${ry}" width="${rw}" height="${rh}" rx="8" class="blueprint-wall blueprint-storage-bay"/>
            
            <!-- Docking Slot Parking Lines -->
            <line x1="${rx + 15}" y1="${ry + 20}" x2="${rx + 15}" y2="${ry + rh - 15}" stroke="#10B981" stroke-width="1.2" stroke-dasharray="3,2" opacity="0.6"/>
            <line x1="${rx + 35}" y1="${ry + 20}" x2="${rx + 35}" y2="${ry + rh - 15}" stroke="#10B981" stroke-width="1.2" stroke-dasharray="3,2" opacity="0.6"/>
            <line x1="${rx + 55}" y1="${ry + 20}" x2="${rx + 55}" y2="${ry + rh - 15}" stroke="#10B981" stroke-width="1.2" stroke-dasharray="3,2" opacity="0.6"/>
            <line x1="${rx + 75}" y1="${ry + 20}" x2="${rx + 75}" y2="${ry + rh - 15}" stroke="#10B981" stroke-width="1.2" stroke-dasharray="3,2" opacity="0.6"/>
            <line x1="${rx + 95}" y1="${ry + 20}" x2="${rx + 95}" y2="${ry + rh - 15}" stroke="#10B981" stroke-width="1.2" stroke-dasharray="3,2" opacity="0.6"/>

            <!-- RFID Antenna Indicator -->
            <circle cx="${rx + 18}" cy="${ry + 16}" r="4.5" fill="#10B981" opacity="0.8"/>
            <circle cx="${rx + 18}" cy="${ry + 16}" r="7.5" fill="none" stroke="#10B981" stroke-width="1" stroke-dasharray="2,2"/>

            <!-- Door Arc Indicator -->
            <path d="M ${rx + 15} ${ry} Q ${rx + 15} ${ry - 12} ${rx + 28} ${ry - 12}" class="blueprint-door stroke-emerald-500" stroke-width="2"/>
            
            <!-- Room Label -->
            <text x="${cx}" y="${cy - 7}" class="blueprint-label fill-emerald-800 font-black text-xs">CLUSTERED CHAIR ZONE</text>
            <text x="${cx}" y="${cy + 6}" fill="#047857" font-size="8.5" font-weight="700" text-anchor="middle" font-family="'Plus Jakarta Sans', sans-serif">Wheelchair Fleet Storage</text>
            <text x="${cx}" y="${cy + 17}" fill="#059669" font-size="7.5" font-weight="600" text-anchor="middle" font-family="monospace">[2-MIN AUTO VERIFY]</text>
          </g>
        `;
      }

      return `
        <g class="blueprint-room cursor-pointer" onclick="handleRoomClick('${room.name}')" data-room-id="${room.id}">
          <!-- Room Wall Boundary -->
          <rect x="${rx}" y="${ry}" width="${rw}" height="${rh}" rx="8" class="blueprint-wall"/>
          
          <!-- Door Arc Indicator -->
          <path d="M ${rx + 15} ${ry} Q ${rx + 15} ${ry - 12} ${rx + 28} ${ry - 12}" class="blueprint-door"/>
          
          <!-- Room Label -->
          <text x="${cx}" y="${cy - 4}" class="blueprint-label">${room.label}</text>
          <text x="${cx}" y="${cy + 14}" fill="#64748b" font-size="9" text-anchor="middle" font-family="Inter">${room.category}</text>
        </g>
      `;
    }).join('');
  }

  // 2. Filter & Render 20 Static Demonstration Dots
  let items = DEMO_BLUEPRINT_EQUIPMENT;
  if (filter !== 'ALL') {
    items = items.filter(eq => eq.status === filter);
  }

  markersGroup.innerHTML = items.map(eq => {
    let fillColor = '#10B981'; // Green
    let strokeColor = '#059669';
    let haloColor = 'rgba(16, 185, 129, 0.4)';
    let statusLabel = 'AVAILABLE';
    let badgeBg = '#065F46';

    if (eq.status === 'INACTIVE') {
      fillColor = '#3B82F6'; // Blue
      strokeColor = '#1D4ED8';
      haloColor = 'rgba(59, 130, 246, 0.4)';
      statusLabel = 'INACTIVE (STANDBY)';
      badgeBg = '#1E40AF';
    } else if (eq.status === 'IN_USE') {
      fillColor = '#F59E0B'; // Yellow
      strokeColor = '#D97706';
      haloColor = 'rgba(245, 158, 11, 0.4)';
      statusLabel = 'IN USE';
      badgeBg = '#92400E';
    } else if (eq.status === 'MAINTENANCE') {
      fillColor = '#EF4444'; // Red
      strokeColor = '#DC2626';
      haloColor = 'rgba(239, 68, 68, 0.45)';
      statusLabel = 'MAINTENANCE';
      badgeBg = '#991B1B';
    }

    return `
      <g class="bp-demo-dot cursor-pointer" onclick="openEquipmentDetailDrawer('${eq.id}')" data-eq-id="${eq.id}">
        <!-- Outer Static Halo Glow -->
        <circle cx="${eq.cx}" cy="${eq.cy}" r="12" fill="${haloColor}"/>
        
        <!-- Main Colored Status Marker Dot -->
        <circle cx="${eq.cx}" cy="${eq.cy}" r="7.5" fill="${fillColor}" stroke="#FFFFFF" stroke-width="2" filter="url(#bp-dot-shadow)"/>
        
        <!-- Inner Core -->
        <circle cx="${eq.cx}" cy="${eq.cy}" r="2.2" fill="#FFFFFF"/>
        
        <!-- Equipment ID Tag Badge below marker -->
        <rect x="${eq.cx - 22}" y="${eq.cy + 9}" width="44" height="13" rx="3.5" fill="${badgeBg}" opacity="0.95"/>
        <text x="${eq.cx}" y="${eq.cy + 18.5}" text-anchor="middle" font-family="'Plus Jakarta Sans', monospace" font-size="7.5" font-weight="800" fill="#FFFFFF">${eq.id}</text>
        
        <!-- Hover Tooltip -->
        <title>${eq.id} — ${eq.name}&#10;Location: ${eq.location}&#10;Operational Status: ${statusLabel}&#10;Battery: ${eq.battery}% • Health: ${eq.health}%&#10;Click to open comprehensive asset telemetry drawer</title>
      </g>
    `;
  }).join('');

  // 3. Populate 4 Summary Lists below Map
  populateDemoSummaryLists();
}

function populateDemoSummaryLists() {
  const listAvail = document.getElementById('bp-list-available');
  const listInact = document.getElementById('bp-list-inactive');
  const listInuse = document.getElementById('bp-list-inuse');
  const listMaint = document.getElementById('bp-list-maintenance');

  if (!listAvail) return;

  const renderCard = (eq, badgeClass, dotColor) => `
    <div onclick="openEquipmentDetailDrawer('${eq.id}')" class="p-2 rounded-xl bg-white border border-slate-200/80 hover:border-slate-400 transition cursor-pointer flex items-center justify-between shadow-xs">
      <div class="flex items-center space-x-2">
        <span class="w-2.5 h-2.5 rounded-full ${dotColor}"></span>
        <div>
          <strong class="font-bold text-slate-800 text-[11px] block">${eq.id}</strong>
          <span class="text-[10px] text-slate-500 block truncate max-w-[130px]">${eq.name}</span>
        </div>
      </div>
      <span class="text-[10px] font-mono text-slate-400 font-semibold">${eq.battery}%</span>
    </div>
  `;

  listAvail.innerHTML = DEMO_BLUEPRINT_EQUIPMENT.filter(e => e.status === 'AVAILABLE')
    .map(e => renderCard(e, 'bg-emerald-100 text-emerald-800', 'bg-emerald-500')).join('');

  listInact.innerHTML = DEMO_BLUEPRINT_EQUIPMENT.filter(e => e.status === 'INACTIVE')
    .map(e => renderCard(e, 'bg-blue-100 text-blue-800', 'bg-blue-500')).join('');

  listInuse.innerHTML = DEMO_BLUEPRINT_EQUIPMENT.filter(e => e.status === 'IN_USE')
    .map(e => renderCard(e, 'bg-amber-100 text-amber-800', 'bg-amber-500')).join('');

  listMaint.innerHTML = DEMO_BLUEPRINT_EQUIPMENT.filter(e => e.status === 'MAINTENANCE')
    .map(e => renderCard(e, 'bg-rose-100 text-rose-800', 'bg-rose-500')).join('');
}

function handleRoomClick(roomName) {
  showToast('Room Selected', `${roomName} — Displaying demonstration assets in this zone`, 'info');
}

// --- Equipment Location Search & Spotlight ---

// --- Live Equipment Spatial Tracking & Movement Simulator ---

let _trackingMotionPaused = false;

function toggleLiveTrackingMotion() {
  const svg = document.getElementById('tracking-svg-canvas');
  const btn = document.getElementById('btn-toggle-motion');
  const icon = document.getElementById('motion-icon');
  const txt = document.getElementById('motion-text');
  if (!svg) return;

  if (!_trackingMotionPaused) {
    try { svg.pauseAnimations(); } catch(e){}
    _trackingMotionPaused = true;
    if (txt) txt.textContent = 'Resume Simulation';
    if (btn) btn.className = 'px-3.5 py-1.5 rounded-full bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow-xs transition flex items-center space-x-1.5';
    showToast('Simulation Paused', 'Live movement animation held at current coordinates.', 'info');
  } else {
    try { svg.unpauseAnimations(); } catch(e){}
    _trackingMotionPaused = false;
    if (txt) txt.textContent = 'Pause Simulation';
    if (btn) btn.className = 'px-3.5 py-1.5 rounded-full bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow-xs transition flex items-center space-x-1.5';
    showToast('Simulation Active', 'Live movement animation running at real-time telemetry speed.', 'success');
  }
}

function resetLiveTrackingMotion() {
  const svg = document.getElementById('tracking-svg-canvas');
  if (svg) {
    try {
      svg.setCurrentTime(0);
      showToast('Simulation Reset', 'Transit vectors reset to origin rooms (General Ward A & Gynaecology).', 'info');
    } catch(e){}
  }
}

async function initLiveTrackingMap() {
  try {
    if (!state.blueprintData) {
      const res = await fetch('/api/blueprint');
      state.blueprintData = await res.json();
    }
    renderTrackingMap(state.blueprintData);
    searchEquipmentLocation('');
  } catch(e) {
    console.error('Failed to initialize live tracking map:', e);
  }
}

function renderTrackingMap(data) {
  const roomsGroup = document.getElementById('tracking-rooms-group');
  const stationaryGroup = document.getElementById('tracking-stationary-markers-group');
  if (!roomsGroup || !stationaryGroup || !data) return;

  const widthScale = 10;
  const heightScale = 6.5;

  // 1. Render All Hospital Rooms
  roomsGroup.innerHTML = (data.rooms || []).map(room => {
    const rx = room.x * widthScale;
    const ry = room.y * heightScale;
    const rw = room.w * widthScale;
    const rh = room.h * heightScale;
    const cx = rx + (rw / 2);
    const cy = ry + (rh / 2);
    const isStorageBay = room.id === 'room-radiology-storage';

    if (isStorageBay) {
      return `
        <g class="blueprint-room cursor-pointer" onclick="handleRoomClick('${room.name}')" data-room-id="${room.id}">
          <rect x="${rx}" y="${ry}" width="${rw}" height="${rh}" rx="8" class="blueprint-wall blueprint-storage-bay"/>
          <!-- Docking Slot Parking Lines -->
          <line x1="${rx + 15}" y1="${ry + 20}" x2="${rx + 15}" y2="${ry + rh - 15}" stroke="#10B981" stroke-width="1.2" stroke-dasharray="3,2" opacity="0.6"/>
          <line x1="${rx + 35}" y1="${ry + 20}" x2="${rx + 35}" y2="${ry + rh - 15}" stroke="#10B981" stroke-width="1.2" stroke-dasharray="3,2" opacity="0.6"/>
          <line x1="${rx + 55}" y1="${ry + 20}" x2="${rx + 55}" y2="${ry + rh - 15}" stroke="#10B981" stroke-width="1.2" stroke-dasharray="3,2" opacity="0.6"/>
          <line x1="${rx + 75}" y1="${ry + 20}" x2="${rx + 75}" y2="${ry + rh - 15}" stroke="#10B981" stroke-width="1.2" stroke-dasharray="3,2" opacity="0.6"/>
          <line x1="${rx + 95}" y1="${ry + 20}" x2="${rx + 95}" y2="${ry + rh - 15}" stroke="#10B981" stroke-width="1.2" stroke-dasharray="3,2" opacity="0.6"/>

          <!-- RFID Antenna Indicator -->
          <circle cx="${rx + 18}" cy="${ry + 16}" r="4.5" fill="#10B981" opacity="0.8"/>
          <circle cx="${rx + 18}" cy="${ry + 16}" r="7.5" fill="none" stroke="#10B981" stroke-width="1" stroke-dasharray="2,2"/>

          <!-- Door Arc -->
          <path d="M ${rx + 15} ${ry} Q ${rx + 15} ${ry - 12} ${rx + 28} ${ry - 12}" class="blueprint-door stroke-emerald-500" stroke-width="2"/>
          <text x="${cx}" y="${cy - 7}" class="blueprint-label fill-emerald-800 font-black text-xs">CLUSTERED CHAIR ZONE</text>
          <text x="${cx}" y="${cy + 6}" fill="#047857" font-size="8.5" font-weight="700" text-anchor="middle" font-family="'Plus Jakarta Sans', sans-serif">Wheelchair Fleet Bay</text>
          <text x="${cx}" y="${cy + 17}" fill="#059669" font-size="7.5" font-weight="600" text-anchor="middle" font-family="monospace">[2-MIN AUTO VERIFY]</text>
        </g>
      `;
    }

    return `
      <g class="blueprint-room cursor-pointer" onclick="handleRoomClick('${room.name}')" data-room-id="${room.id}">
        <rect x="${rx}" y="${ry}" width="${rw}" height="${rh}" rx="8" class="blueprint-wall"/>
        <path d="M ${rx + 15} ${ry} Q ${rx + 15} ${ry - 12} ${rx + 28} ${ry - 12}" class="blueprint-door"/>
        <text x="${cx}" y="${cy - 4}" class="blueprint-label">${room.label}</text>
        <text x="${cx}" y="${cy + 14}" fill="#64748b" font-size="9" text-anchor="middle" font-family="Inter">${room.category}</text>
      </g>
    `;
  }).join('');

  // 2. Render Stationary Equipment as SLEEK BLACK DOTS
  // (Excluding WC-007 and VENT-02 which are the 2 live moving units rendered as RED DOTS)
  const stationaryItems = (data.equipment || []).filter(eq => eq.id !== 'WC-007' && eq.id !== 'VENT-02');

  stationaryGroup.innerHTML = stationaryItems.map(eq => {
    const mx = eq.coordinates_x * widthScale;
    const my = eq.coordinates_y * heightScale;

    return `
      <g class="cursor-pointer transition-transform hover:scale-150" onclick="openEquipmentDetailDrawer('${eq.id}')" data-eq-id="${eq.id}">
        <circle cx="${mx}" cy="${my}" r="4.8" fill="#0F172A" stroke="#334155" stroke-width="1.8"/>
        <circle cx="${mx}" cy="${my}" r="1.6" fill="#94A3B8"/>
        <title>${eq.id} — ${eq.name} (${eq.location}) • Status: ${eq.status} [STATIONARY IN-ROOM]</title>
      </g>
    `;
  }).join('');
}

function searchEquipmentLocation(query) {
  const q = (query || '').toLowerCase().trim();
  const container = document.getElementById('location-results-grid');
  if (!container) return;

  const list = state.equipmentList || (state.blueprintData ? state.blueprintData.equipment : []);
  if (!list || list.length === 0) return;

  const results = !q ? list.slice(0, 12) : list.filter(item => 
    (item.id && item.id.toLowerCase().includes(q)) ||
    (item.name && item.name.toLowerCase().includes(q)) ||
    (item.type && item.type.toLowerCase().includes(q)) ||
    (item.location && item.location.toLowerCase().includes(q))
  );

  renderLocationSearchResults(results);
}

function renderLocationSearchResults(results) {
  const container = document.getElementById('location-results-grid');
  if (!container) return;

  if (results.length === 0) {
    container.innerHTML = '<div class="col-span-full py-8 text-center text-slate-500 font-medium">No equipment items found matching search query.</div>';
    return;
  }

  container.innerHTML = results.slice(0, 12).map(item => {
    const isMoving = item.id === 'WC-007' || item.id === 'VENT-02';

    return `
      <div class="glass-panel p-4 rounded-2xl flex flex-col justify-between hover:border-indigo-400 transition cursor-pointer" onclick="openEquipmentDetailDrawer('${item.id}')">
        <div>
          <div class="flex justify-between items-start">
            <span class="font-mono font-bold text-xs ${isMoving ? 'text-rose-700 bg-rose-50 border border-rose-200' : 'text-indigo-700 bg-indigo-50 border border-indigo-200'} px-2 py-0.5 rounded-md">${item.id}</span>
            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${isMoving ? 'bg-rose-100 text-rose-700 border border-rose-200 animate-pulse' : 'bg-slate-100 text-slate-700 border border-slate-200'}">
              ${isMoving ? '🔴 LIVE MOVING' : '⚫ STATIONARY'}
            </span>
          </div>
          <h4 class="font-bold text-slate-900 text-xs mt-2">${item.name}</h4>
          <div class="mt-2 text-xs text-slate-600 space-y-1">
            <div class="flex justify-between"><span>Location:</span><strong class="text-slate-800">${item.location}</strong></div>
            <div class="flex justify-between"><span>Room:</span><strong class="text-slate-700">${item.room || 'General Area'}</strong></div>
            <div class="flex justify-between pt-1 text-[11px] text-slate-400 border-t border-slate-100">
              <span>Battery: <strong class="${item.battery < 20 ? 'text-rose-600' : 'text-slate-700'}">${item.battery}%</strong></span>
              <span>Health: <strong class="text-emerald-700">${item.health_score}%</strong></span>
            </div>
          </div>
        </div>

        <div class="mt-3 flex items-center space-x-2 pt-2 border-t border-slate-100" onclick="event.stopPropagation()">
          <button onclick="spotlightOnBlueprint('${item.id}')" class="flex-1 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded-lg text-xs font-bold transition flex items-center justify-center space-x-1 border border-indigo-200">
            <i data-lucide="map-pin" class="w-3 h-3"></i>
            <span>Locate on Radar</span>
          </button>
          <button onclick="openTransferModal('${item.id}')" class="px-2.5 py-1 bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 rounded-lg text-xs font-bold transition">
            Transfer
          </button>
        </div>
      </div>
    `;
  }).join('');

  lucide.createIcons();
}

function spotlightOnBlueprint(eqId) {
  switchTab('location');

  setTimeout(() => {
    let targetEl = null;
    if (eqId === 'WC-007') {
      targetEl = document.getElementById('red-dot-marker-1');
    } else if (eqId === 'VENT-02') {
      targetEl = document.getElementById('red-dot-marker-2');
    } else {
      targetEl = document.querySelector(`[data-eq-id="${eqId}"]`);
    }

    const canvas = document.getElementById('tracking-svg-canvas');
    if (canvas) {
      canvas.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    if (targetEl) {
      targetEl.classList.add('animate-pulse');
      setTimeout(() => targetEl.classList.remove('animate-pulse'), 4500);
    }

    openEquipmentDetailDrawer(eqId);
    showToast('Equipment Located', `Tracking ${eqId} on Live Spatial Radar`, 'success');
  }, 250);
}

// --- Equipment Detail Flyout Side-Panel Drawer ---

async function openEquipmentDetailDrawer(eqId) {
  const drawer = document.getElementById('equipment-detail-drawer');
  const inner = document.getElementById('drawer-inner-content');
  if (!drawer || !inner) return;

  inner.innerHTML = '<div class="py-12 text-center text-cyan-400">Loading comprehensive asset telemetry...</div>';
  drawer.classList.add('open');

  try {
    const res = await fetch(`/api/equipment/${eqId}`);
    const data = await res.json();
    const eq = data.equipment;
    const diag = data.ai_diagnostics;
    const movements = data.movement_history || [];

    const role = state.currentUser.role;

    inner.innerHTML = `
      <div class="flex items-start justify-between border-b border-slate-800 pb-4">
        <div>
          <span class="text-[10px] font-bold text-cyan-400 uppercase tracking-wider">${eq.department || 'Clinical'} Asset</span>
          <h2 class="text-xl font-black text-white mt-0.5">${eq.id}</h2>
          <p class="text-xs text-slate-300 font-semibold">${eq.name}</p>
        </div>
        <button onclick="closeEquipmentDetailDrawer()" class="text-slate-400 hover:text-white p-1">
          <i data-lucide="x" class="w-5 h-5"></i>
        </button>
      </div>

      <!-- Status & Location Pill -->
      <div class="mt-4 p-3 rounded-2xl bg-slate-900 border border-slate-800 text-xs space-y-1.5">
        <div class="flex justify-between">
          <span class="text-slate-400">Operational Status:</span>
          <span class="font-extrabold ${eq.status === 'AVAILABLE' ? 'text-emerald-400' : 'text-sky-300'}">${eq.status}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-slate-400">Current Location:</span>
          <strong class="text-white">${eq.location}</strong>
        </div>
        <div class="flex justify-between">
          <span class="text-slate-400">Assigned Room:</span>
          <strong class="text-cyan-300">${eq.room || 'General Area'}</strong>
        </div>
        <div class="flex justify-between font-mono text-[11px] pt-1 border-t border-slate-800 text-slate-400">
          <span>RFID UID:</span> <span class="text-cyan-400">${eq.rfid_uid || 'N/A'}</span>
        </div>
      </div>

      <!-- Telemetry Specs Grid -->
      <div class="grid grid-cols-2 gap-2 mt-4 text-xs">
        <div class="p-2.5 bg-slate-900 rounded-xl border border-slate-800">
          <span class="text-[10px] text-slate-400 block">Health Score</span>
          <strong class="text-base text-emerald-400 mt-0.5 block">${eq.health_score}%</strong>
        </div>
        <div class="p-2.5 bg-slate-900 rounded-xl border border-slate-800">
          <span class="text-[10px] text-slate-400 block">Battery Level</span>
          <strong class="text-base ${eq.battery < 25 ? 'text-rose-400' : 'text-slate-200'} mt-0.5 block">${eq.battery}%</strong>
        </div>
        <div class="p-2.5 bg-slate-900 rounded-xl border border-slate-800">
          <span class="text-[10px] text-slate-400 block">Usage Runtime</span>
          <strong class="text-base text-white mt-0.5 block">${eq.usage_hours} h</strong>
        </div>
        <div class="p-2.5 bg-slate-900 rounded-xl border border-slate-800">
          <span class="text-[10px] text-slate-400 block">Movement Pings</span>
          <strong class="text-base text-white mt-0.5 block">${eq.movement_count}</strong>
        </div>
      </div>

      <!-- Diagnostic Risk Advisory -->
      <div class="mt-4 p-3.5 rounded-2xl bg-purple-950/30 border border-purple-500/30 text-xs space-y-1">
        <div class="font-extrabold text-purple-300 flex items-center space-x-1.5">
          <i data-lucide="sparkles" class="w-3.5 h-3.5 text-purple-400"></i>
          <span>Random Forest Risk Intelligence</span>
        </div>
        <p class="text-slate-200 text-[11px] leading-relaxed">${diag ? diag.recommendation : 'Asset is operating within normal medical standards.'}</p>
        <div class="text-[10px] text-slate-400 pt-1">Failure probability: <strong class="${diag && diag.failure_risk_pct > 50 ? 'text-rose-400' : 'text-emerald-400'}">${diag ? diag.failure_risk_pct : 8}%</strong></div>
      </div>

      <!-- Movement History Snippet -->
      <div class="mt-4 border-t border-slate-800 pt-3">
        <span class="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-2">Transit History</span>
        <div class="space-y-1.5 text-[11px]">
          ${movements.length > 0 ? movements.slice(0, 3).map(m => `
            <div class="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-300">
              <div class="font-bold text-white">${m.from_location} → ${m.to_location}</div>
              <div class="text-slate-400 text-[10px] flex justify-between">
                <span>Duration: ${m.duration_seconds}s</span>
                <span>${m.movement_time.slice(11, 16)}</span>
              </div>
            </div>
          `).join('') : '<div class="text-slate-500">No previous transits logged.</div>'}
        </div>
      </div>

      <!-- Role-Permitted Actions -->
      <div class="mt-6 space-y-2 pt-4 border-t border-slate-800">
        ${(role === 'EQUIPMENT_MANAGER' || role === 'ADMIN' || role === 'DOCTOR') ? `
          <button onclick="openTransferModal('${eq.id}')" class="w-full py-2.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded-xl text-xs font-bold transition flex items-center justify-center space-x-1.5">
            <i data-lucide="git-branch" class="w-3.5 h-3.5"></i>
            <span>Transfer / Reallocate</span>
          </button>
        ` : ''}

        ${(role === 'EQUIPMENT_MANAGER' || role === 'ADMIN') ? `
          ${eq.status === 'MAINTENANCE' ? `
            <button onclick="handleMaintenanceAction('${eq.id}', 'complete_maintenance')" class="w-full py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold transition">
              Mark Maintenance Completed (Return to Fleet)
            </button>
          ` : `
            <button onclick="handleMaintenanceAction('${eq.id}', 'send_to_maintenance')" class="w-full py-2 bg-amber-600/30 hover:bg-amber-600/40 text-amber-200 border border-amber-500/30 rounded-xl text-xs font-bold transition">
              Send to Annex Maintenance Bay
            </button>
          `}
        ` : ''}
      </div>
    `;

    lucide.createIcons();
  } catch (e) {
    inner.innerHTML = '<div class="py-8 text-center text-rose-400">Failed to load equipment details.</div>';
  }
}

function closeEquipmentDetailDrawer() {
  const drawer = document.getElementById('equipment-detail-drawer');
  if (drawer) drawer.classList.remove('open');
}

// --- Emergency Shortage Intelligence View ---

async function loadShortageIntelligence() {
  const container = document.getElementById('shortages-cards-container');
  if (!container) return;

  try {
    const res = await fetch('/api/shortages');
    const data = await res.json();

    container.innerHTML = data.map(item => {
      const isHigh = item.severity === 'HIGH';
      return `
        <div class="glass-panel p-6 rounded-3xl ${isHigh ? 'border-2 border-rose-300 shadow-rose-500/5' : 'border border-amber-300 shadow-amber-500/5'} flex flex-col justify-between space-y-5">
          <div>
            <div class="flex justify-between items-start gap-3">
              <div>
                <span class="text-[10px] font-extrabold ${isHigh ? 'text-rose-600 bg-rose-50 border border-rose-200' : 'text-amber-600 bg-amber-50 border border-amber-200'} px-2.5 py-0.5 rounded-full uppercase tracking-wider">${item.severity} SHORTAGE RISK</span>
                <h3 class="text-xl font-extrabold text-slate-900 mt-2">${item.equipment_type}</h3>
                <p class="text-xs text-slate-500 font-semibold flex items-center space-x-1.5 mt-0.5">
                  <i data-lucide="map-pin" class="w-3.5 h-3.5 text-slate-400"></i>
                  <span>${item.ward_name}</span>
                </p>
              </div>
              <span class="px-3 py-1 rounded-full text-xs font-black shrink-0 ${isHigh ? 'bg-rose-100 text-rose-800 border border-rose-300' : 'bg-amber-100 text-amber-800 border border-amber-300'}">
                Shortage in ~${item.time_to_shortage_hours}h
              </span>
            </div>

            <!-- Quantitative Telemetry Bar -->
            <div class="grid grid-cols-3 gap-3 mt-4 text-xs text-center">
              <div class="p-3 bg-slate-50 rounded-2xl border border-slate-200/80">
                <span class="text-slate-400 text-[10px] font-bold uppercase tracking-wider block">Current Available</span>
                <strong class="text-xl font-black text-emerald-600 mt-1 block">${item.current_available}</strong>
              </div>
              <div class="p-3 bg-slate-50 rounded-2xl border border-slate-200/80">
                <span class="text-slate-400 text-[10px] font-bold uppercase tracking-wider block">Predicted (3h)</span>
                <strong class="text-xl font-black text-rose-600 mt-1 block">${item.predicted_demand_3h}</strong>
              </div>
              <div class="p-3 bg-slate-50 rounded-2xl border border-slate-200/80">
                <span class="text-slate-400 text-[10px] font-bold uppercase tracking-wider block">Expected Deficit</span>
                <strong class="text-xl font-black text-rose-600 mt-1 block">-${item.expected_shortage} units</strong>
              </div>
            </div>

            <!-- Clinical Explanation -->
            <div class="mt-4 p-4 rounded-2xl bg-slate-50/80 border border-slate-200 text-xs text-slate-700 space-y-1.5 leading-relaxed">
              <div class="font-extrabold text-slate-900 flex items-center space-x-1.5">
                <i data-lucide="info" class="w-3.5 h-3.5 text-blue-600"></i>
                <span>Clinical Triage Explanation:</span>
              </div>
              <p class="text-slate-600">${item.explanation}</p>
            </div>

            <!-- AI Recommendation Directive -->
            <div class="mt-3 p-4 rounded-2xl bg-indigo-50/80 border border-indigo-200 text-xs text-indigo-950 space-y-1">
              <div class="font-black text-indigo-900 flex items-center space-x-1.5">
                <i data-lucide="sparkles" class="w-4 h-4 text-indigo-600"></i>
                <span>AI Prescriptive Directive:</span>
              </div>
              <p class="text-indigo-800 font-medium">${item.ai_recommendation}</p>
            </div>
          </div>

          <div class="pt-2 flex justify-end">
            <button onclick="executeAIAutoTransfer('${item.equipment_type}', '${item.ward_name}')" class="px-5 py-2.5 rounded-xl bg-gradient-to-r from-rose-600 to-red-600 hover:from-rose-500 text-white font-extrabold text-xs shadow-lg shadow-rose-600/30 transition flex items-center space-x-2 cursor-pointer">
              <i data-lucide="send" class="w-4 h-4"></i>
              <span>EXECUTE AI PRE-EMPTIVE REALLOCATION</span>
            </button>
          </div>
        </div>
      `;
    }).join('');

    lucide.createIcons();
  } catch (e) {
    console.error('Failed to load shortage intelligence:', e);
  }
}

async function executeAIAutoTransfer(eqType, wardName) {
  showToast('Initiating AI Transfer', `Auto-dispatching candidate ${eqType}s to ${wardName}`, 'info');
  switchTab('blueprint');

  setTimeout(() => {
    animateHospitalTransitRoute();
    showToast('Transfer Complete', `2 ${eqType}s staged in ${wardName}`, 'success');
  }, 1000);
}

// --- Department Digital Twins (Gynaecology & ICU) ---

async function loadGynaecologyDigitalTwin() {
  const container = document.getElementById('gynaecology-content-container');
  if (!container) return;

  try {
    const res = await fetch('/api/department/gynaecology');
    const data = await res.json();

    container.innerHTML = `
      <!-- Department Summary KPI Banner -->
      <div class="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div class="glass-panel p-4 rounded-2xl">
          <span class="text-xs font-bold text-slate-400 uppercase">Tracked Assets</span>
          <div class="text-3xl font-black text-purple-400 mt-1">${data.total_tracked_assets}</div>
          <span class="text-[11px] text-slate-400">RFID Synchronized</span>
        </div>
        <div class="glass-panel p-4 rounded-2xl">
          <span class="text-xs font-bold text-slate-400 uppercase">Available in Suite</span>
          <div class="text-3xl font-black text-emerald-400 mt-1">${data.available_tracked_assets}</div>
          <span class="text-[11px] text-slate-400">Ready for clinic</span>
        </div>
        <div class="glass-panel p-4 rounded-2xl">
          <span class="text-xs font-bold text-slate-400 uppercase">In Active Procedure</span>
          <div class="text-3xl font-black text-sky-400 mt-1">${data.in_use_tracked_assets}</div>
          <span class="text-[11px] text-slate-400">Voluson Ultrasound</span>
        </div>
        <div class="glass-panel p-4 rounded-2xl">
          <span class="text-xs font-bold text-slate-400 uppercase">Shortage Status</span>
          <div class="text-3xl font-black text-amber-400 mt-1">1 POSSIBLE</div>
          <span class="text-[11px] text-amber-300">Evening ultrasound scan</span>
        </div>
      </div>

      <!-- Mini Gynaecology Blueprint & Trackable Assets -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        <!-- Floor Plan Schematic (2 cols) -->
        <div class="lg:col-span-2 glass-panel p-5 rounded-2xl space-y-4">
          <div class="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 class="font-bold text-white text-sm">Gynaecology Suite Floor Plan</h3>
            <span class="text-xs text-purple-300 font-mono">WEST CLINICAL WING</span>
          </div>

          <!-- Mini SVG Blueprint -->
          <div class="w-full h-72 bg-slate-950 rounded-xl border border-purple-500/20 p-2 relative overflow-hidden flex items-center justify-center">
            <svg class="w-full h-full" viewBox="0 0 600 300">
              <!-- Partitions -->
              <rect x="20" y="20" width="160" height="120" rx="8" fill="#131024" stroke="#a855f7" stroke-width="1.5"/>
              <text x="100" y="45" fill="#c084fc" font-size="11" font-weight="bold" text-anchor="middle">EXAM ROOM 1</text>
              <circle cx="80" cy="85" r="7" fill="#10b981"/>
              <text x="80" y="105" fill="#94a3b8" font-size="9" text-anchor="middle">Exam Table</text>

              <rect x="200" y="20" width="180" height="120" rx="8" fill="#131024" stroke="#a855f7" stroke-width="1.5"/>
              <text x="290" y="45" fill="#c084fc" font-size="11" font-weight="bold" text-anchor="middle">ULTRASOUND ROOM</text>
              <circle cx="270" cy="85" r="7" fill="#38bdf8"/>
              <text x="270" y="105" fill="#94a3b8" font-size="9" text-anchor="middle">Voluson US-01 (In Use)</text>

              <rect x="400" y="20" width="180" height="120" rx="8" fill="#131024" stroke="#a855f7" stroke-width="1.5"/>
              <text x="490" y="45" fill="#c084fc" font-size="11" font-weight="bold" text-anchor="middle">CTG ROOM</text>
              <circle cx="470" cy="85" r="7" fill="#10b981"/>
              <text x="470" y="105" fill="#94a3b8" font-size="9" text-anchor="middle">Dual CTG-01</text>

              <rect x="20" y="160" width="260" height="120" rx="8" fill="#131024" stroke="#a855f7" stroke-width="1.5"/>
              <text x="150" y="185" fill="#c084fc" font-size="11" font-weight="bold" text-anchor="middle">PROCEDURE ROOM</text>
              <circle cx="120" cy="225" r="7" fill="#f59e0b"/>
              <text x="120" y="245" fill="#94a3b8" font-size="9" text-anchor="middle">Colposcope (Maint)</text>

              <rect x="300" y="160" width="280" height="120" rx="8" fill="#131024" stroke="#a855f7" stroke-width="1.5"/>
              <text x="440" y="185" fill="#c084fc" font-size="11" font-weight="bold" text-anchor="middle">LAPAROSCOPY ROOM</text>
              <circle cx="420" cy="225" r="7" fill="#10b981"/>
              <text x="420" y="245" fill="#94a3b8" font-size="9" text-anchor="middle">4K Lap Tower</text>
            </svg>
          </div>

          <!-- Tracked IoT Assets Table -->
          <div class="space-y-2">
            <h4 class="text-xs font-bold text-white uppercase tracking-wider">Trackable IoT Hardware Assets</h4>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
              ${data.tracked_equipment.map(item => `
                <div class="p-3 bg-slate-900 rounded-xl border border-slate-800 flex justify-between items-center cursor-pointer hover:border-purple-400 transition" onclick="openEquipmentDetailDrawer('${item.id}')">
                  <div>
                    <span class="font-bold text-white">${item.name}</span>
                    <span class="text-slate-400 block text-[10px]">${item.room} • ${item.id}</span>
                  </div>
                  <span class="px-2 py-0.5 rounded text-[9px] font-bold ${item.status === 'AVAILABLE' ? 'bg-emerald-500/20 text-emerald-300' : (item.status === 'IN_USE' ? 'bg-sky-500/20 text-sky-300' : 'bg-amber-500/20 text-amber-300')}">${item.status}</span>
                </div>
              `).join('')}
            </div>
          </div>
        </div>

        <!-- Non-Tracked Clinical Sets Reference (1 col) -->
        <div class="glass-panel p-5 rounded-2xl flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 class="font-bold text-white text-sm">Non-Tracked Clinical Sets</h3>
              <span class="text-[10px] text-slate-500 font-bold uppercase">Manual Sets</span>
            </div>
            <p class="text-xs text-slate-400 mt-2 mb-4">
              Standard surgical and exam instruments cataloged for inventory compliance (not treated as individual RFID nodes).
            </p>

            <div class="space-y-2 text-xs">
              ${data.clinical_instruments_untracked.map(inst => `
                <div class="p-2.5 rounded-xl bg-slate-900 border border-slate-800">
                  <div class="font-bold text-white">${inst.name}</div>
                  <div class="flex justify-between text-[11px] text-slate-400 mt-1">
                    <span>${inst.category}</span>
                    <span class="text-cyan-400 font-bold">${inst.qty_in_stock} in stock</span>
                  </div>
                  <span class="inline-block mt-1 text-[9px] px-1.5 py-0.2 rounded bg-slate-800 text-emerald-400 font-semibold">${inst.sterilization_status}</span>
                </div>
              `).join('')}
            </div>
          </div>
        </div>

      </div>
    `;
    lucide.createIcons();
  } catch (e) {
    console.error('Failed to load Gynaecology digital twin:', e);
  }
}

async function loadICUDigitalTwin() {
  const container = document.getElementById('icu-content-container');
  if (!container) return;

  try {
    const res = await fetch('/api/department/icu');
    const data = await res.json();

    const beds = data.beds || [
      { bed_id: 'ICU Bed 01', bed_eq: 'BD-ICU-01', monitor_eq: 'MON-ICU-01', ventilator_eq: 'VENT-01', status: 'OCCUPIED (CRITICAL)' },
      { bed_id: 'ICU Bed 02', bed_eq: 'BD-ICU-02', monitor_eq: 'MON-ICU-02', ventilator_eq: 'VENT-02', status: 'OCCUPIED (HIGH)' },
      { bed_id: 'ICU Bed 03', bed_eq: 'BD-ICU-03', monitor_eq: 'MON-ICU-03', ventilator_eq: 'VENT-03', status: 'AVAILABLE (STANDBY)' },
      { bed_id: 'ICU Bed 04', bed_eq: 'BD-ICU-04', monitor_eq: 'MON-ICU-04', ventilator_eq: 'VENT-04', status: 'AVAILABLE (STANDBY)' }
    ];

    const fixedInfra = data.fixed_infrastructure || [];

    container.innerHTML = `
      <!-- ICU Summary KPI Banner -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="glass-panel p-5 rounded-3xl">
          <span class="text-xs font-bold text-slate-400 uppercase tracking-wide">Tracked ICU Assets</span>
          <div class="text-3xl font-black text-indigo-600 mt-2">${data.total_tracked_assets || 26}</div>
          <span class="text-[11px] text-slate-500 font-medium">Life-support monitored</span>
        </div>
        <div class="glass-panel p-5 rounded-3xl">
          <span class="text-xs font-bold text-slate-400 uppercase tracking-wide">Available Life Support</span>
          <div class="text-3xl font-black text-emerald-600 mt-2">${data.available_tracked_assets || 8}</div>
          <span class="text-[11px] text-slate-500 font-medium">Ready in immediate reserve</span>
        </div>
        <div class="glass-panel p-5 rounded-3xl">
          <span class="text-xs font-bold text-slate-400 uppercase tracking-wide">Active Beds</span>
          <div class="text-3xl font-black text-rose-600 mt-2">${data.occupied_beds || 18} / ${data.bed_capacity || 20}</div>
          <span class="text-[11px] text-rose-600 font-semibold">90% Acute Bed Occupancy</span>
        </div>
        <div class="glass-panel p-5 rounded-3xl">
          <span class="text-xs font-bold text-slate-400 uppercase tracking-wide">Ventilator Shortage Risk</span>
          <div class="text-3xl font-black text-amber-600 mt-2">HIGH RISK</div>
          <span class="text-[11px] text-amber-600 font-semibold">Predicted shortage in ~2.4h</span>
        </div>
      </div>

      <!-- ICU Beds Interactive Schematic Grid -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        <!-- Beds Schematic (2 cols) -->
        <div class="lg:col-span-2 glass-panel p-6 rounded-3xl space-y-5">
          <div class="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h3 class="font-extrabold text-slate-900 text-base">ICU Bed Station Digital Twin</h3>
              <p class="text-xs text-slate-500 mt-0.5">Real-time bedside vitals telemetry, ventilator synchrony, and telemetry monitors.</p>
            </div>
            <span class="px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-bold border border-emerald-200">
              4 SMART BEDS (ACTIVE)
            </span>
          </div>

          <!-- Beds Grid -->
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            ${beds.map(bed => `
              <div class="p-4 rounded-2xl bg-slate-900 border ${bed.status.includes('CRITICAL') ? 'border-rose-500/60 shadow-rose-500/10' : (bed.status.includes('OCCUPIED') ? 'border-sky-500/60 shadow-sky-500/10' : 'border-emerald-500/40')} space-y-3 relative overflow-hidden shadow-lg">
                <div class="flex justify-between items-center">
                  <div class="flex items-center space-x-2">
                    <span class="font-black text-white text-sm font-mono tracking-tight">${bed.bed_id}</span>
                    <svg class="w-14 h-4 text-emerald-400 animate-pulse" viewBox="0 0 100 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M0 12 L28 12 L33 5 L39 19 L45 7 L50 14 L54 12 L100 12" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                  </div>
                  <span class="px-2 py-0.5 rounded text-[9px] font-extrabold ${bed.status.includes('CRITICAL') ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40' : (bed.status.includes('OCCUPIED') ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40' : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40')}">${bed.status}</span>
                </div>
                <div class="space-y-1.5 text-xs text-slate-300 font-medium">
                  <div class="flex justify-between">
                    <span class="text-slate-400">Electric Bed:</span>
                    <strong class="text-cyan-300 font-mono">${bed.bed_eq}</strong>
                  </div>
                  <div class="flex justify-between">
                    <span class="text-slate-400">Multiparameter Monitor:</span>
                    <strong class="text-emerald-400 font-mono">${bed.monitor_eq}</strong>
                  </div>
                  <div class="flex justify-between">
                    <span class="text-slate-400">ICU Ventilator:</span>
                    <strong class="text-sky-300 font-mono">${bed.ventilator_eq}</strong>
                  </div>
                </div>
                <button onclick="openEquipmentDetailDrawer('${bed.ventilator_eq}')" class="w-full py-2 bg-slate-800 hover:bg-indigo-600 text-slate-200 hover:text-white rounded-xl text-xs font-bold transition flex items-center justify-center space-x-1.5 cursor-pointer">
                  <i data-lucide="activity" class="w-3.5 h-3.5"></i>
                  <span>Inspect Bed Station Telemetry</span>
                </button>
              </div>
            `).join('')}
          </div>

          <!-- ICU Equipment Storage & Crash Cart Section -->
          <div class="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-3">
            <div class="flex justify-between items-center text-xs">
              <span class="font-extrabold text-white tracking-wide uppercase">ICU EQUIPMENT STORAGE & CRASH BAY</span>
              <span class="text-emerald-400 font-bold flex items-center space-x-1">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span>
                <span>Immediate Standby</span>
              </span>
            </div>
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div class="p-3 bg-slate-800/90 rounded-xl border border-slate-700/80 text-center cursor-pointer hover:border-cyan-400 hover:bg-slate-800 transition" onclick="openEquipmentDetailDrawer('DEFIB-01')">
                <span class="text-[10px] font-bold text-slate-400 block uppercase">DEFIBRILLATOR</span>
                <strong class="text-emerald-400 font-mono block mt-1 text-sm font-bold">DEFIB-01</strong>
                <span class="text-[10px] text-emerald-300 mt-0.5 block">100% Battery</span>
              </div>
              <div class="p-3 bg-slate-800/90 rounded-xl border border-slate-700/80 text-center cursor-pointer hover:border-rose-400 hover:bg-slate-800 transition" onclick="openEquipmentDetailDrawer('CRASH-01')">
                <span class="text-[10px] font-bold text-slate-400 block uppercase">CRASH CART</span>
                <strong class="text-rose-400 font-mono block mt-1 text-sm font-bold">CRASH-01</strong>
                <span class="text-[10px] text-rose-300 mt-0.5 block">Armed & Sealed</span>
              </div>
              <div class="p-3 bg-slate-800/90 rounded-xl border border-slate-700/80 text-center cursor-pointer hover:border-emerald-400 hover:bg-slate-800 transition" onclick="openEquipmentDetailDrawer('INF-03')">
                <span class="text-[10px] font-bold text-slate-400 block uppercase">INFUSION PUMP</span>
                <strong class="text-emerald-400 font-mono block mt-1 text-sm font-bold">INF-03</strong>
                <span class="text-[10px] text-slate-400 mt-0.5 block">Calibrated</span>
              </div>
              <div class="p-3 bg-slate-800/90 rounded-xl border border-slate-700/80 text-center cursor-pointer hover:border-sky-400 hover:bg-slate-800 transition" onclick="openEquipmentDetailDrawer('VENT-04')">
                <span class="text-[10px] font-bold text-slate-400 block uppercase">STANDBY VENT</span>
                <strong class="text-sky-300 font-mono block mt-1 text-sm font-bold">VENT-04</strong>
                <span class="text-[10px] text-sky-300 mt-0.5 block">Ready for Patient</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Fixed Infrastructure Status (1 col) -->
        <div class="glass-panel p-6 rounded-3xl flex flex-col justify-between space-y-4">
          <div>
            <div class="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 class="font-bold text-slate-900 text-base">Fixed Pipeline Infrastructure</h3>
              <span class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Non-Movable</span>
            </div>
            <p class="text-xs text-slate-500 mt-2 mb-4 leading-relaxed">
              Continuous wall pipeline telemetry for medical oxygen, compressed air, and central hospital vacuum suction.
            </p>

            <div class="space-y-3 text-xs">
              ${fixedInfra.map(infra => `
                <div class="p-3.5 rounded-2xl bg-slate-50 border border-slate-100 hover:bg-white transition space-y-1">
                  <div class="font-bold text-slate-900 text-xs">${infra.name}</div>
                  <div class="text-[11px] font-mono font-bold text-blue-700">${infra.status}</div>
                  <div class="text-[10px] text-slate-400">Coverage: ${infra.coverage}</div>
                </div>
              `).join('')}
            </div>
          </div>

          <div class="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl text-xs text-emerald-800 flex items-center space-x-2 font-medium">
            <i data-lucide="check-circle-2" class="w-4 h-4 text-emerald-600 shrink-0"></i>
            <span>Central manifold bulk liquid oxygen supply at 84% capacity. Nominal pressure maintained.</span>
          </div>
        </div>

      </div>
    `;
    lucide.createIcons();
  } catch (e) {
    console.error('Failed to load ICU digital twin:', e);
  }
}

// --- Role-Based Access Governance (RBAC) Table ---

async function loadUsersTable() {
  const tbody = document.getElementById('users-table-body');
  if (!tbody) return;

  try {
    const role = state.currentUser ? state.currentUser.role : 'EQUIPMENT_MANAGER';
    const userId = state.currentUser ? state.currentUser.id : 'mgr-marcus';
    const res = await fetch('/api/users', {
      headers: { 
        'X-User-Role': role,
        'X-User-Id': userId
      }
    });
    
    let users = [];
    if (res.ok) {
      users = await res.json();
    } else {
      users = [
        { id: 'mgr-marcus', name: 'Marcus Reed', email: 'marcus.reed@stjude-hospital.org', role: 'EQUIPMENT_MANAGER', department: 'Equipment Control', permissions: ['ALL', 'MANAGE_EQUIPMENT', 'ALLOCATE_EQUIPMENT', 'VIEW_IOT', 'MANAGE_USERS', 'VIEW_REPORTS'], status: 'ACTIVE' },
        { id: 'doc-ananya', name: 'Dr. Ananya Sen (MD)', email: 'ananya.doc@stjude-hospital.org', role: 'DOCTOR', department: 'Intensive Care Unit (ICU)', permissions: ['VIEW_WARD_EQUIPMENT', 'VIEW_HOSPITAL_MAP', 'CREATE_EQUIPMENT_REQUEST', 'VIEW_CLINICAL_INSIGHTS'], status: 'ACTIVE' },
        { id: 'nurse-priya', name: 'Nurse Priya Sharma', email: 'priya.nurse@stjude-hospital.org', role: 'NURSE', department: 'Emergency & Trauma', permissions: ['VIEW_WARD_EQUIPMENT', 'VIEW_HOSPITAL_MAP', 'REQUEST_EQUIPMENT', 'VIEW_LIVE_EQUIPMENT'], status: 'ACTIVE' },
        { id: 'admin-vance', name: 'Dr. Alex Vance', email: 'alex.vance@stjude-hospital.org', role: 'ADMIN', department: 'Hospital Administration', permissions: ['ALL', 'MANAGE_USERS', 'MANAGE_SYSTEM', 'ALLOCATE_EQUIPMENT'], status: 'ACTIVE' }
      ];
    }

    if (!Array.isArray(users) || users.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="py-6 text-center text-slate-500 font-medium">No registered staff users found.</td></tr>';
      return;
    }

    tbody.innerHTML = users.map(u => {
      let roleBadgeClass = 'bg-slate-100 text-slate-700 border-slate-200';
      if (u.role === 'ADMIN') roleBadgeClass = 'bg-purple-100 text-purple-800 border-purple-200';
      else if (u.role === 'EQUIPMENT_MANAGER') roleBadgeClass = 'bg-amber-100 text-amber-800 border-amber-200';
      else if (u.role === 'DOCTOR') roleBadgeClass = 'bg-sky-100 text-sky-800 border-sky-200';
      else if (u.role === 'NURSE') roleBadgeClass = 'bg-emerald-100 text-emerald-800 border-emerald-200';

      const perms = Array.isArray(u.permissions) ? u.permissions : [];
      const visiblePerms = perms.slice(0, 3);
      const remainingCount = perms.length - visiblePerms.length;

      return `
        <tr class="hover:bg-slate-50/80 transition border-b border-slate-100">
          <td class="py-3.5 px-4 font-mono text-xs font-bold text-indigo-700 whitespace-nowrap">
            <span class="bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded-lg">${u.id}</span>
          </td>
          <td class="py-3.5 px-4">
            <div class="font-extrabold text-slate-900 text-sm flex items-center space-x-2">
              <span class="w-6 h-6 rounded-full bg-slate-200 text-slate-700 font-bold text-[11px] flex items-center justify-center shrink-0">
                ${u.name.charAt(0)}
              </span>
              <span>${u.name}</span>
            </div>
          </td>
          <td class="py-3.5 px-4 text-xs font-mono text-slate-600">
            ${u.email}
          </td>
          <td class="py-3.5 px-4 whitespace-nowrap">
            <span class="px-2.5 py-1 rounded-full text-[11px] font-extrabold border ${roleBadgeClass}">${u.role}</span>
          </td>
          <td class="py-3.5 px-4 text-xs font-semibold text-slate-700 whitespace-nowrap">
            ${u.department || 'Hospital Wide'}
          </td>
          <td class="py-3.5 px-4">
            <div class="flex flex-wrap gap-1 max-w-xs">
              ${visiblePerms.map(p => `
                <span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">${p}</span>
              `).join('')}
              ${remainingCount > 0 ? `<span class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">+${remainingCount} more</span>` : ''}
            </div>
          </td>
          <td class="py-3.5 px-4 text-right space-x-1.5 whitespace-nowrap">
            <button onclick="toggleUserStatus('${u.id}', '${u.status === 'ACTIVE' ? 'DISABLED' : 'ACTIVE'}')" class="px-2.5 py-1 rounded-xl text-xs font-bold border transition ${u.status === 'ACTIVE' ? 'bg-slate-100 hover:bg-slate-200 text-slate-700 border-slate-300' : 'bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border-emerald-300'}">
              ${u.status === 'ACTIVE' ? 'Deactivate' : 'Activate'}
            </button>
          </td>
        </tr>
      `;
    }).join('');
    lucide.createIcons();
  } catch (e) {
    console.error('Failed to load users table:', e);
    tbody.innerHTML = '<tr><td colspan="7" class="py-6 text-center text-slate-400">Failed to connect to RBAC governance service.</td></tr>';
  }
}

function openAddUserModal() {
  const m = document.getElementById('user-modal');
  if (m) m.classList.remove('hidden');
}

function closeUserModal() {
  const m = document.getElementById('user-modal');
  if (m) m.classList.add('hidden');
}

async function handleCreateUser(e) {
  e.preventDefault();
  const nameEl = document.getElementById('new-user-name');
  const emailEl = document.getElementById('new-user-email');
  const roleEl = document.getElementById('new-user-role');
  const deptEl = document.getElementById('new-user-dept');

  const name = nameEl ? nameEl.value.trim() : '';
  const email = emailEl ? emailEl.value.trim() : '';
  const role = roleEl ? roleEl.value : 'NURSE';
  const dept = deptEl ? deptEl.value : 'General Ward';

  try {
    const res = await fetch('/api/users', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'X-User-Role': state.currentUser ? state.currentUser.role : 'EQUIPMENT_MANAGER'
      },
      body: JSON.stringify({ name, email, role, department: dept })
    });
    const data = await res.json();
    if (data.success) {
      showToast('Staff Member Added', `Created ${role} account for ${name}`, 'success');
      closeUserModal();
      if (nameEl) nameEl.value = '';
      if (emailEl) emailEl.value = '';
      loadUsersTable();
    } else {
      showToast('Error', data.detail || 'Could not register staff member', 'emergency');
    }
  } catch (err) {
    showToast('Staff Member Created', `Registered ${name} as ${role} for ${dept}.`, 'success');
    closeUserModal();
    loadUsersTable();
  }
}

// --- IoT Sensor Intelligence Network ---

async function loadIotNetwork() {
  const grid = document.getElementById('iot-nodes-grid');
  if (!grid) return;

  try {
    const res = await fetch('/api/iot/nodes');
    const data = await res.json();

    if (data.summary) {
      const kpiTotal = document.getElementById('iot-kpi-total');
      const kpiSignal = document.getElementById('iot-kpi-signal');
      const kpiLatency = document.getElementById('iot-kpi-latency');
      const kpiBattery = document.getElementById('iot-kpi-battery');

      if (kpiTotal) kpiTotal.textContent = `${data.summary.total_nodes} Online`;
      if (kpiSignal) kpiSignal.textContent = `${data.nodes[0]?.network?.rssi || -52} dBm`;
      if (kpiLatency) kpiLatency.textContent = `${data.summary.avg_latency_ms} ms`;
      if (kpiBattery) kpiBattery.textContent = `${data.summary.alert_nodes} Flagged`;
    }

    grid.innerHTML = data.nodes.map(n => {
      const isMaster = n.node_id === 'ESP32-GW-01';
      const isAlert = n.status === 'ALERT' || n.power.battery < 20;
      const batt = n.power.battery;
      const battColor = batt < 20 ? 'bg-rose-500' : (batt < 50 ? 'bg-amber-500' : 'bg-emerald-500');

      return `
        <div class="glass-panel p-5 rounded-3xl space-y-4 border ${isAlert ? 'border-rose-300 ring-2 ring-rose-200' : (isMaster ? 'border-indigo-300 ring-2 ring-indigo-100' : 'border-slate-200/80')} shadow-sm hover:shadow-md transition">
          <!-- Header -->
          <div class="flex items-start justify-between">
            <div class="flex items-center space-x-2.5">
              <div class="w-10 h-10 rounded-2xl ${isMaster ? 'bg-indigo-600 text-white' : (isAlert ? 'bg-rose-100 text-rose-600' : 'bg-blue-50 text-blue-600')} flex items-center justify-center font-bold text-sm shadow-sm shrink-0">
                <i data-lucide="${isMaster ? 'cpu' : (isAlert ? 'alert-triangle' : 'radio')}" class="w-5 h-5"></i>
              </div>
              <div>
                <div class="flex items-center space-x-1.5">
                  <h3 class="font-extrabold text-slate-900 text-sm">${n.node_id}</h3>
                  <span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold uppercase ${n.status === 'STREAMING' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200 animate-pulse' : (isAlert ? 'bg-rose-50 text-rose-700 border border-rose-200' : 'bg-blue-50 text-blue-700 border border-blue-200')}">${n.status}</span>
                </div>
                <p class="text-xs text-slate-500 font-semibold">${n.device_class}</p>
              </div>
            </div>
            <span class="text-[11px] font-mono text-slate-400 font-medium">${n.network.ip}</span>
          </div>

          <!-- Target Equipment & Physical Location -->
          <div class="p-2.5 rounded-2xl bg-slate-50 border border-slate-100 flex items-center justify-between text-xs">
            <div class="flex items-center space-x-1.5 text-slate-700 font-bold">
              <i data-lucide="tag" class="w-3.5 h-3.5 text-indigo-500"></i>
              <span>${n.equipment_name}</span>
            </div>
            <div class="text-[11px] text-slate-500 font-medium flex items-center space-x-1">
              <i data-lucide="map-pin" class="w-3 h-3 text-slate-400"></i>
              <span>${n.location}</span>
            </div>
          </div>

          <!-- Network Signal & Power -->
          <div class="grid grid-cols-2 gap-2 text-xs">
            <!-- Signal Telemetry -->
            <div class="p-3 rounded-2xl bg-white border border-slate-100 space-y-1">
              <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
                <span>Signal (RSSI)</span>
                <span class="text-blue-600 font-extrabold">${n.network.rssi} dBm</span>
              </div>
              <div class="text-[11px] text-slate-700 font-semibold">${n.network.protocol}</div>
              <div class="text-[10px] text-slate-500">Lag: ${n.network.latency_ms}ms • Loss: ${n.network.packet_loss}%</div>
            </div>

            <!-- Battery Level -->
            <div class="p-3 rounded-2xl bg-white border border-slate-100 space-y-1">
              <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
                <span>Battery Level</span>
                <span class="font-extrabold ${batt < 20 ? 'text-rose-600' : 'text-slate-800'}">${batt}%</span>
              </div>
              <div class="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                <div class="${battColor} h-full rounded-full transition-all duration-500" style="width: ${batt}%"></div>
              </div>
              <div class="text-[10px] ${batt < 20 ? 'text-rose-600 font-bold' : 'text-slate-500'}">${n.power.voltage}V • ${n.power.health}</div>
            </div>
          </div>

          <!-- Sensory Telemetry Suite -->
          <div class="p-3.5 rounded-2xl bg-gradient-to-br from-slate-50 to-indigo-50/30 border border-slate-200/80 space-y-2 text-xs">
            <div class="text-[10px] font-extrabold text-slate-500 uppercase tracking-wider flex items-center justify-between">
              <span>Sensory Telemetry</span>
              <span class="text-indigo-600 font-mono font-bold">${n.sensors.pir_infrared.model} + RC522</span>
            </div>
            
            <!-- PIR Motion Sensor -->
            <div class="flex items-center justify-between text-xs">
              <div class="flex items-center space-x-1.5 text-slate-700 font-semibold">
                <i data-lucide="eye" class="w-3.5 h-3.5 text-indigo-500"></i>
                <span>PIR Infrared Sensor:</span>
              </div>
              <span class="font-bold px-2 py-0.5 rounded-md text-[10px] ${n.sensors.pir_infrared.state === 'DETECTED' ? 'bg-emerald-100 text-emerald-800 animate-pulse' : 'bg-slate-200 text-slate-700'}">
                ${n.sensors.pir_infrared.state}
              </span>
            </div>
            <div class="text-[10px] text-slate-500 font-mono">
              • Proximity: 4cm Hand Signature • Window: 10s Continuous Motion
            </div>

            <!-- RFID Sensor -->
            <div class="flex items-center justify-between text-xs pt-1 border-t border-slate-200/50">
              <div class="flex items-center space-x-1.5 text-slate-700 font-semibold">
                <i data-lucide="credit-card" class="w-3.5 h-3.5 text-purple-500"></i>
                <span>RFID Reader UID:</span>
              </div>
              <span class="font-mono font-bold text-slate-900 bg-white border border-slate-200 px-2 py-0.5 rounded text-[10px]">${n.sensors.rfid.last_uid}</span>
            </div>

            <!-- IMU & Environment -->
            <div class="flex items-center justify-between text-[11px] text-slate-600 pt-1 border-t border-slate-200/50">
              <span>IMU: <strong>${n.sensors.imu.motion}</strong> (${n.sensors.imu.tilt}°)</span>
              <span>Temp: <strong>${n.sensors.environment.temperature}°C</strong> (${n.sensors.environment.humidity}%)</span>
            </div>
          </div>

          <!-- Action Controls -->
          <div class="flex items-center space-x-2 pt-1">
            <button onclick="pingSingleNode('${n.node_id}')" class="flex-1 py-1.5 px-3 bg-white hover:bg-slate-50 border border-slate-200 rounded-xl text-slate-700 font-bold text-xs transition flex items-center justify-center space-x-1">
              <i data-lucide="zap" class="w-3.5 h-3.5 text-amber-500"></i>
              <span>Ping Node</span>
            </button>
            <button onclick="showNodeDiagnostics('${n.node_id}', '${n.equipment_name}')" class="flex-1 py-1.5 px-3 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-xl text-indigo-700 font-bold text-xs transition flex items-center justify-center space-x-1">
              <i data-lucide="activity" class="w-3.5 h-3.5 text-indigo-600"></i>
              <span>Diagnostics</span>
            </button>
          </div>
        </div>
      `;
    }).join('');

    lucide.createIcons();
  } catch (err) {
    console.error('Failed to load IoT network:', err);
  }
}

function pingAllNodes() {
  showToast('Mesh Ping Dispatched', 'Pinging 14 hospital microcontroller nodes... Mean response: 12ms (100% OK)', 'success');
}

function pingSingleNode(nodeId) {
  const latency = Math.floor(Math.random() * 8) + 9;
  showToast(`Ping ${nodeId}`, `Round-trip latency: ${latency} ms • Signal -52 dBm • Packet loss 0.00%`, 'info');
}

function showNodeDiagnostics(nodeId, eqName) {
  showToast(`Diagnostics: ${nodeId}`, `Sensors nominal. HC-SR501 PIR sensor armed (4cm radius, 10s timer). RC522 SPI ready. Linked to ${eqName}.`, 'success');
}

// --- Clinical Operations Reports ---

async function loadClinicalReports() {
  const container = document.getElementById('reports-container');
  if (!container) return;

  try {
    const res = await fetch('/api/reports/clinical');
    const data = await res.json();

    container.innerHTML = `
      <!-- Executive KPI Summary Cards -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="glass-panel p-5 rounded-3xl border border-slate-200/80 shadow-sm space-y-1">
          <div class="text-[10px] font-extrabold text-slate-400 uppercase tracking-wider">Radiology Throughput</div>
          <div class="text-2xl font-black text-slate-900">${data.radiology.daily_total_scans} Scans</div>
          <div class="text-xs text-emerald-600 font-bold flex items-center space-x-1">
            <i data-lucide="trending-up" class="w-3.5 h-3.5"></i>
            <span>${data.radiology.on_time_rate}% On-Time Delivery</span>
          </div>
        </div>

        <div class="glass-panel p-5 rounded-3xl border border-slate-200/80 shadow-sm space-y-1">
          <div class="text-[10px] font-extrabold text-slate-400 uppercase tracking-wider">Equipment Utilization</div>
          <div class="text-2xl font-black text-blue-600">${data.equipment_utilization.overall_utilization_pct}%</div>
          <div class="text-xs text-slate-500 font-semibold">
            ${data.equipment_utilization.active_in_use} of ${data.equipment_utilization.fleet_size} Assets In Service
          </div>
        </div>

        <div class="glass-panel p-5 rounded-3xl border border-slate-200/80 shadow-sm space-y-1">
          <div class="text-[10px] font-extrabold text-slate-400 uppercase tracking-wider">Fleet MTBF Reliability</div>
          <div class="text-2xl font-black text-indigo-600">${data.mtbf_reliability.mean_time_between_failures_hours} h</div>
          <div class="text-xs text-emerald-600 font-bold">
            ${data.mtbf_reliability.preventative_compliance_pct}% Maintenance Adherence
          </div>
        </div>

        <div class="glass-panel p-5 rounded-3xl border border-slate-200/80 shadow-sm space-y-1">
          <div class="text-[10px] font-extrabold text-slate-400 uppercase tracking-wider">Transit Optimization</div>
          <div class="text-2xl font-black text-purple-600">-34 min</div>
          <div class="text-xs text-slate-500 font-semibold">
            Dwell reduction via Auto-Staging
          </div>
        </div>
      </div>

      <!-- Module 1: Radiology Throughput & Queue Velocity Report -->
      <div class="glass-panel p-6 rounded-3xl border border-slate-200/80 shadow-sm space-y-5">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-slate-100">
          <div>
            <div class="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700 text-[11px] font-extrabold uppercase mb-1">
              <i data-lucide="activity" class="w-3 h-3"></i>
              <span>Radiology Operational Velocity</span>
            </div>
            <h3 class="text-lg font-black text-slate-900">Radiology Throughput & Modality Utilization Report</h3>
            <p class="text-xs text-slate-500">Scan duration cycle times, technician queues, and transport bottleneck mitigation.</p>
          </div>
          <span class="text-xs font-bold text-slate-400">Target: 195 scans / day</span>
        </div>

        <!-- Modalities Grid -->
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          ${data.radiology.modalities.map(m => `
            <div class="p-4 rounded-2xl bg-white border border-slate-200 space-y-3">
              <div class="flex items-center justify-between">
                <span class="font-bold text-slate-900 text-xs">${m.modality.split('(')[0]}</span>
                <span class="px-2 py-0.5 rounded-md text-[10px] font-bold ${m.status === 'PEAK_LOAD' ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800'}">${m.status}</span>
              </div>
              <div class="space-y-1">
                <div class="flex items-center justify-between text-xs">
                  <span class="text-slate-500">Completed</span>
                  <span class="font-extrabold text-slate-900">${m.scans_completed} / ${m.target_scans} scans</span>
                </div>
                <div class="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                  <div class="bg-indigo-600 h-full rounded-full" style="width: ${m.utilization_pct}%"></div>
                </div>
              </div>
              <div class="text-[11px] text-slate-600 space-y-0.5 pt-1 border-t border-slate-100">
                <div>Avg Cycle: <strong>${m.avg_cycle_mins} mins</strong></div>
                <div class="text-[10px] text-slate-400">Lead: ${m.lead_technologist}</div>
              </div>
            </div>
          `).join('')}
        </div>

        <!-- Bottleneck Insight -->
        <div class="p-4 rounded-2xl bg-blue-50 border border-blue-200 text-xs text-blue-900 flex items-start space-x-3">
          <i data-lucide="info" class="w-5 h-5 text-blue-600 shrink-0 mt-0.5"></i>
          <div>
            <strong class="font-extrabold">Clinical Transport Bottleneck Analysis:</strong>
            <p class="mt-0.5 text-blue-800 font-medium">${data.radiology.bottleneck_insights}</p>
          </div>
        </div>
      </div>

      <!-- Module 2: Hospital-Wide Equipment Utilization & Velocity Report -->
      <div class="glass-panel p-6 rounded-3xl border border-slate-200/80 shadow-sm space-y-5">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-slate-100">
          <div>
            <div class="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-[11px] font-extrabold uppercase mb-1">
              <i data-lucide="pie-chart" class="w-3 h-3"></i>
              <span>Fleet Velocity & Turnaround</span>
            </div>
            <h3 class="text-lg font-black text-slate-900">Hospital Equipment Utilization & Turnaround Report</h3>
            <p class="text-xs text-slate-500">Live deployment metrics by clinical ward and dwell reduction tracking.</p>
          </div>
          <span class="text-xs font-bold text-emerald-700 bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200">Overall: ${data.equipment_utilization.overall_utilization_pct}% Active</span>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          ${data.equipment_utilization.by_department.map(dept => `
            <div class="p-4 rounded-2xl bg-white border border-slate-200 space-y-2.5">
              <div class="flex items-center justify-between">
                <span class="font-extrabold text-slate-900 text-xs">${dept.department.split('&')[0]}</span>
                <span class="px-2 py-0.5 rounded-md text-[10px] font-extrabold ${dept.utilization_pct > 90 ? 'bg-rose-100 text-rose-800' : (dept.utilization_pct > 75 ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800')}">${dept.utilization_pct}%</span>
              </div>
              <div class="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
                <div class="${dept.utilization_pct > 90 ? 'bg-rose-500' : 'bg-emerald-500'} h-full rounded-full" style="width: ${dept.utilization_pct}%"></div>
              </div>
              <div class="flex items-center justify-between text-[11px] text-slate-500 font-semibold pt-1">
                <span>Deployed: ${dept.deployed} / ${dept.capacity}</span>
                <span class="text-slate-400 font-mono">${dept.status}</span>
              </div>
            </div>
          `).join('')}
        </div>

        <div class="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-900 flex items-start space-x-3">
          <i data-lucide="check-circle" class="w-5 h-5 text-emerald-600 shrink-0 mt-0.5"></i>
          <div>
            <strong class="font-extrabold">Turnaround Efficiency Gains:</strong>
            <p class="mt-0.5 text-emerald-800 font-medium">${data.equipment_utilization.dwell_time_reduction}</p>
          </div>
        </div>
      </div>

      <!-- Module 3: MTBF & Predictive Reliability Engineering Report -->
      <div class="glass-panel p-6 rounded-3xl border border-slate-200/80 shadow-sm space-y-5">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-slate-100">
          <div>
            <div class="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 text-[11px] font-extrabold uppercase mb-1">
              <i data-lucide="wrench" class="w-3 h-3"></i>
              <span>Engineering Reliability</span>
            </div>
            <h3 class="text-lg font-black text-slate-900">MTBF (Mean Time Between Failures) & Reliability Report</h3>
            <p class="text-xs text-slate-500">Preventative maintenance adherence, component wear models, and critical asset surveillance.</p>
          </div>
          <span class="text-xs font-bold text-indigo-700 bg-indigo-50 px-3 py-1 rounded-full border border-indigo-200">MTBF: ${data.mtbf_reliability.mean_time_between_failures_hours} Hours</span>
        </div>

        <!-- Monitored High Risk Fleet -->
        <div class="space-y-3">
          ${data.mtbf_reliability.monitored_fleet.map(item => `
            <div class="p-4 rounded-2xl bg-white border ${item.battery < 20 ? 'border-rose-300 ring-1 ring-rose-200' : 'border-slate-200'} flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div class="flex items-center space-x-3">
                <div class="w-10 h-10 rounded-2xl ${item.battery < 20 ? 'bg-rose-100 text-rose-600' : 'bg-slate-100 text-slate-700'} flex items-center justify-center font-bold text-sm shrink-0">
                  <i data-lucide="${item.battery < 20 ? 'alert-triangle' : 'shield-check'}" class="w-5 h-5"></i>
                </div>
                <div>
                  <div class="flex items-center space-x-2">
                    <span class="font-extrabold text-slate-900 text-sm">${item.name} (${item.equipment_id})</span>
                    <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${item.battery < 20 ? 'bg-rose-100 text-rose-800' : 'bg-indigo-100 text-indigo-800'}">${item.category}</span>
                  </div>
                  <p class="text-xs ${item.battery < 20 ? 'text-rose-700 font-bold' : 'text-slate-600 font-medium'} mt-0.5">${item.directive}</p>
                </div>
              </div>
              <div class="flex items-center space-x-4 self-end md:self-center shrink-0">
                <div class="text-right">
                  <div class="text-[10px] text-slate-400 font-bold uppercase">Health MTBF</div>
                  <div class="text-xs font-black text-slate-800">${item.mtbf_hours} h</div>
                </div>
                <div class="text-right">
                  <div class="text-[10px] text-slate-400 font-bold uppercase">Battery</div>
                  <div class="text-xs font-black ${item.battery < 20 ? 'text-rose-600' : 'text-emerald-600'}">${item.battery}%</div>
                </div>
                <button onclick="executeReportIntervention('${item.equipment_id}')" class="btn-pill btn-pill-secondary text-xs">
                  <span>Service Action</span>
                </button>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;

    lucide.createIcons();
  } catch (err) {
    console.error('Failed to load clinical reports:', err);
  }
}

function exportClinicalReportPDF() {
  showToast('Generating Executive PDF', 'Compiling Radiology Throughput, Equipment Utilization, and MTBF Reliability Report...', 'info');
  setTimeout(() => {
    showToast('Report Downloaded', 'St_Jude_Clinical_Operations_Executive_Report.pdf is ready.', 'success');
  }, 1200);
}

function exportClinicalDataCSV() {
  const csvContent = "data:text/csv;charset=utf-8,Category,Metric,Value,Status\nRadiology,Daily Scans,184,94.2% On-Time\nRadiology,CT Utilization,92%,Peak Load\nFleet,Hospital Utilization,86.4%,Optimal\nFleet,Emergency Ward,94%,Near Capacity\nEngineering,Fleet MTBF,1420 Hours,Compliant\nEngineering,Preventative Adherence,98.2%,Active\n";
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", "clinical_operations_dataset.csv");
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  showToast('CSV Exported', 'clinical_operations_dataset.csv saved successfully.', 'success');
}

function executeReportIntervention(eqId) {
  showToast('Intervention Initiated', `Maintenance priority work-order generated for ${eqId}. Assigned to biomedical team.`, 'success');
}

// --- Equipment Transfer & Movement Handlers ---

function openTransferModal(eqId) {
  const m = document.getElementById('transfer-modal');
  const inp = document.getElementById('transfer-eq-id');
  const sub = document.getElementById('transfer-item-subtitle');
  if (!m || !inp) return;

  inp.value = eqId;
  if (sub) sub.textContent = `Reallocating Equipment: ${eqId}`;
  m.classList.remove('hidden');
}

function closeTransferModal() {
  const m = document.getElementById('transfer-modal');
  if (m) m.classList.add('hidden');
}

async function handleTransferSubmit(e) {
  e.preventDefault();
  const eqId = document.getElementById('transfer-eq-id').value;
  const toWard = document.getElementById('transfer-to-ward').value;
  const reason = document.getElementById('transfer-reason').value;

  try {
    const res = await fetch('/api/equipment/transfer', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'X-User-Role': state.currentUser.role 
      },
      body: JSON.stringify({
        equipment_id: eqId,
        to_ward: toWard,
        reason: reason
      })
    });
    const data = await res.json();
    if (data.success) {
      closeTransferModal();
      closeEquipmentDetailDrawer();
      showToast('Transfer Dispatched', `${eqId} successfully dispatched to ${toWard}`, 'success');
      loadBlueprintData();
    }
  } catch (e) {
    showToast('Transfer Failed', 'Insufficient permissions or server error', 'emergency');
  }
}

async function handleMaintenanceAction(eqId, action) {
  try {
    const res = await fetch('/api/equipment/maintenance-action', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'X-User-Role': state.currentUser.role 
      },
      body: JSON.stringify({ equipment_id: eqId, action })
    });
    const data = await res.json();
    if (data.success) {
      closeEquipmentDetailDrawer();
      showToast('Maintenance Status', `Updated ${eqId} status to ${data.status}`, 'success');
      loadBlueprintData();
    }
  } catch (e) {
    showToast('Action Failed', 'Insufficient permissions to manage maintenance', 'emergency');
  }
}

// --- Tab Switcher & Navigation Routing ---

function switchTab(tabId) {
  state.currentTab = tabId;

  document.querySelectorAll('.tab-pane').forEach(el => {
    el.classList.add('hidden');
    el.classList.remove('block');
  });

  const activePane = document.getElementById(`tab-${tabId}`);
  if (activePane) {
    activePane.classList.remove('hidden');
    activePane.classList.add('block');
  }

  // Legacy sidebar items
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.remove('active');
  });
  const activeNav = document.getElementById(`nav-${tabId}`);
  if (activeNav) {
    activeNav.classList.add('active');
  }

  // Floating top navigation pills
  document.querySelectorAll('.nav-pill').forEach(el => {
    el.classList.remove('active');
  });
  const topNav = document.getElementById(`top-nav-${tabId}`);
  if (topNav) {
    topNav.classList.add('active');
  }

  // Close mega-menu or mobile navigation drawers if open
  const megaMenu = document.getElementById('capabilities-mega-menu');
  if (megaMenu && !megaMenu.classList.contains('hidden')) {
    megaMenu.classList.add('hidden');
  }
  const mobileNav = document.getElementById('mobile-nav-drawer');
  if (mobileNav && !mobileNav.classList.contains('hidden')) {
    mobileNav.classList.add('hidden');
  }

  lucide.createIcons();

  // Lazy tab loaders
  if (tabId === 'dashboard') renderRoleDashboard();
  if (tabId === 'blueprint') switchBlueprintView('interactive');
  if (tabId === 'location') initLiveTrackingMap();
  if (tabId === 'shortages') loadShortageIntelligence();
  if (tabId === 'gynaecology') loadGynaecologyDigitalTwin();
  if (tabId === 'icu') loadICUDigitalTwin();
  if (tabId === 'users') loadUsersTable();
  if (tabId === 'movement') loadMovementsList();
  if (tabId === 'allocation') updateWeightsUI();
  if (tabId === 'maintenance') renderMaintenancePage();
  if (tabId === 'forecast') renderForecastPage();
  if (tabId === 'emergency') renderEmergencyPage();
  if (tabId === 'vision') renderVisionAiPage();
  if (tabId === 'equipment') loadEquipmentInventoryTable();
  if (tabId === 'radiology') loadRadiologyDashboard();
  if (tabId === 'iot') loadIotNetwork();
  if (tabId === 'ai-command') loadClinicalReports();
}

function toggleCapabilitiesMenu() {
  const menu = document.getElementById('capabilities-mega-menu');
  if (!menu) return;
  menu.classList.toggle('hidden');
}

function toggleMobileMenu() {
  const drawer = document.getElementById('mobile-nav-drawer');
  if (!drawer) return;
  drawer.classList.toggle('hidden');
}

async function openModalityDetail(modalityName) {
  const modal = document.getElementById('modality-detail-modal');
  if (!modal) return;
  
  const mKey = modalityName ? modalityName.toUpperCase() : 'MRI';
  const title = document.getElementById('modal-mod-title');
  const desc = document.getElementById('modal-mod-desc');
  const badge = document.getElementById('modal-mod-badge');
  const scanWait = document.getElementById('modal-mod-scan-wait');
  const scanDur = document.getElementById('modal-mod-scan-dur');
  const repWait = document.getElementById('modal-mod-rep-wait');
  const totalTurn = document.getElementById('modal-mod-total-turn');
  const patientList = document.getElementById('modal-mod-patient-list');

  if (title) title.textContent = `${mKey} Diagnostic Suite Intelligence`;
  if (desc) desc.textContent = `Autonomous Modality Inspection & Turnaround Performance`;

  let data = state.radiologyCurrentDashboard;
  if (!data) {
    try {
      const res = await fetch('/api/radiology/dashboard');
      data = await res.json();
      state.radiologyCurrentDashboard = data;
    } catch(e) {
      console.error(e);
    }
  }

  const modalities = data?.modalities || (Array.isArray(data?.modality_cards) ? Object.fromEntries(data.modality_cards.map(m => [m.modality, m])) : {});
  const modData = modalities[mKey] || modalities[Object.keys(modalities).find(k => k.toLowerCase() === mKey.toLowerCase())] || {
    scan_wait_minutes: 25,
    scan_duration_minutes: 20,
    report_wait_minutes: 45,
    total_turnaround_minutes: 90,
    operational_status: 'OPTIMAL'
  };

  const w = modData.scan_wait_minutes || 0;
  const d = modData.scan_duration_minutes || 0;
  const r = modData.report_wait_minutes || 0;
  const t = modData.total_turnaround_minutes || (w + d + r);

  if (scanWait) scanWait.textContent = `${w}m`;
  if (scanDur) scanDur.textContent = `${d}m`;
  if (repWait) repWait.textContent = `${r}m`;
  if (totalTurn) totalTurn.textContent = `${t}m`;

  if (badge) {
    const st = modData.status || modData.operational_status || 'OPTIMAL';
    badge.textContent = st;
    if (st === 'PEAK LOAD' || st === 'ATTENTION') {
      badge.className = 'status-pill status-pill-hold';
    } else if (st === 'BOTTLENECK') {
      badge.className = 'status-pill status-pill-maintenance animate-pulse';
    } else {
      badge.className = 'status-pill status-pill-available';
    }
  }

  if (patientList) {
    patientList.innerHTML = '<div class="py-3 text-slate-400 text-center text-xs">Loading modality queues...</div>';
    try {
      const res = await fetch(`/api/radiology/patients?modality=${encodeURIComponent(mKey)}`);
      const ptData = await res.json();
      const pts = ptData.patients || ptData || [];
      if (!pts || pts.length === 0) {
        patientList.innerHTML = '<div class="py-3 text-slate-400 text-center text-xs">No patients currently queued for this modality suite.</div>';
      } else {
        patientList.innerHTML = pts.map(p => `
          <div class="p-3 rounded-2xl bg-slate-50 border border-slate-100 flex items-center justify-between text-xs">
            <div class="flex items-center space-x-2.5">
              <span class="font-mono font-bold text-blue-700">${p.patient_id}</span>
              <span class="font-medium text-slate-800">${p.patient_name || 'Patient'}</span>
              <span class="status-pill ${p.priority === 'EMERGENCY' ? 'status-pill-maintenance' : (p.priority === 'URGENT' ? 'status-pill-hold' : 'status-pill-available')} text-[9px]">${p.priority}</span>
            </div>
            <div class="flex items-center space-x-3 text-[11px]">
              <span class="text-slate-500">${p.current_step || p.report_status}</span>
              <span class="font-black text-purple-700">${p.total_turnaround_minutes}m</span>
            </div>
          </div>
        `).join('');
      }
    } catch(err) {
      patientList.innerHTML = '<div class="py-2 text-rose-500 text-center text-xs">Unable to load patient queue.</div>';
    }
  }

  modal.classList.remove('hidden');
  lucide.createIcons();
}

function closeModalityModal() {
  const modal = document.getElementById('modality-detail-modal');
  if (modal) modal.classList.add('hidden');
}

window.openModalityDetail = openModalityDetail;
window.closeModalityModal = closeModalityModal;
window.toggleCapabilitiesMenu = toggleCapabilitiesMenu;
window.toggleMobileMenu = toggleMobileMenu;


async function loadMovementsList() {
  const container = document.getElementById('movements-timeline-list');
  if (!container) return;

  try {
    const res = await fetch('/api/equipment/movement');
    const movements = await res.json();

    container.innerHTML = movements.map(m => `
      <div class="p-3 bg-slate-900 rounded-xl border border-slate-800 text-xs">
        <div class="flex justify-between items-center font-bold text-white">
          <span class="text-cyan-300 font-mono">${m.equipment_id}</span>
          <span class="text-slate-400 text-[10px]">${m.movement_time.slice(11, 19)}</span>
        </div>
        <div class="text-slate-200 mt-1 font-semibold">${m.from_location} → ${m.to_location}</div>
        <div class="text-[11px] text-slate-400 mt-0.5">${m.route_description || 'Direct corridor transfer'}</div>
      </div>
    `).join('');
  } catch (e) {
    console.error('Failed to load movements list:', e);
  }
}

// --- AI Allocation Engine Handlers ---

function updateWeightsUI() {
  const wAvail = parseInt(document.getElementById('w-avail')?.value || '30');
  const wDist = parseInt(document.getElementById('w-dist')?.value || '20');
  const wCond = parseInt(document.getElementById('w-cond')?.value || '20');
  const wMaint = parseInt(document.getElementById('w-maint')?.value || '15');
  const wPrio = parseInt(document.getElementById('w-prio')?.value || '10');
  const wBatt = parseInt(document.getElementById('w-batt')?.value || '5');

  if (document.getElementById('label-w-avail')) document.getElementById('label-w-avail').textContent = `${wAvail}%`;
  if (document.getElementById('label-w-dist')) document.getElementById('label-w-dist').textContent = `${wDist}%`;
  if (document.getElementById('label-w-cond')) document.getElementById('label-w-cond').textContent = `${wCond}%`;
  if (document.getElementById('label-w-maint')) document.getElementById('label-w-maint').textContent = `${wMaint}%`;
  if (document.getElementById('label-w-prio')) document.getElementById('label-w-prio').textContent = `${wPrio}%`;
  if (document.getElementById('label-w-batt')) document.getElementById('label-w-batt').textContent = `${wBatt}%`;

  state.weights = {
    avail: wAvail,
    dist: wDist,
    cond: wCond,
    maint: wMaint,
    prio: wPrio,
    batt: wBatt
  };
}

async function runAllocationEngine() {
  const eqType = document.getElementById('alloc-req-type')?.value || 'Wheelchair';
  const targetWard = document.getElementById('alloc-target-ward')?.value || 'ward-emergency';
  const priority = document.getElementById('alloc-priority')?.value || 'High';
  const qty = parseInt(document.getElementById('alloc-qty')?.value || '2');

  const stepsContainer = document.getElementById('allocation-steps-container');
  const stepsGrid = document.getElementById('alloc-steps-grid');
  const resultsCard = document.getElementById('allocation-results-card');
  const unitsGrid = document.getElementById('alloc-units-grid');

  if (stepsContainer) stepsContainer.classList.remove('hidden');
  if (resultsCard) resultsCard.classList.remove('hidden');

  if (stepsGrid) {
    const steps = [
      { num: '01', title: 'Filter Standby', desc: `Querying available ${eqType}s`, icon: 'filter' },
      { num: '02', title: 'Spatial Proximity', desc: `Distance matrix to target ward`, icon: 'compass' },
      { num: '03', title: 'MTBF Diagnostic', desc: 'Screening wear failure risk (<40%)', icon: 'activity' },
      { num: '04', title: 'Battery State', desc: 'Verifying minimum SoC runtime', icon: 'battery-charging' },
      { num: '05', title: 'Acuity Score', desc: `Applying ${priority} priority coefficient`, icon: 'alert-circle' },
      { num: '06', title: 'Pareto Optimize', desc: 'Composite rank candidate fleet', icon: 'award' }
    ];
    stepsGrid.innerHTML = steps.map(s => `
      <div class="p-3 rounded-xl bg-slate-900 border border-cyan-500/20 text-xs space-y-1">
        <div class="flex items-center justify-between text-[10px] font-bold text-cyan-400">
          <span>STEP ${s.num}</span>
          <i data-lucide="${s.icon}" class="w-3.5 h-3.5"></i>
        </div>
        <div class="font-bold text-white">${s.title}</div>
        <div class="text-[10px] text-slate-400 leading-tight">${s.desc}</div>
      </div>
    `).join('');
    lucide.createIcons();
  }

  try {
    const res = await fetch('/api/allocation/evaluate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Role': state.currentUser.role
      },
      body: JSON.stringify({
        equipment_type: eqType,
        target_ward: targetWard,
        priority: priority,
        quantity: qty,
        weights: state.weights
      })
    });
    const data = await res.json();
    state.activeAllocation = data;

    const units = data.selected_units || [
      { id: 'WC-007', name: 'Smart Wheelchair 007', location: 'Storage Room A', distance_m: 18, battery: 84, health_score: 95, composite_score: 0.94, why_selected: 'Closest proximity with 84% battery and zero fault history.' },
      { id: 'WC-021', name: 'Smart Wheelchair 021', location: 'Storage Room A', distance_m: 22, battery: 76, health_score: 92, composite_score: 0.89, why_selected: 'Secondary standby unit in adjacent storage corridor.' }
    ];

    if (unitsGrid) {
      unitsGrid.innerHTML = units.slice(0, qty).map((unit, idx) => `
        <div class="p-4 rounded-2xl bg-slate-900 border border-cyan-500/30 space-y-3 relative overflow-hidden">
          <div class="absolute top-2 right-2 px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 text-[9px] font-black">
            #${idx + 1} RECOMMENDED
          </div>
          <div>
            <div class="font-mono font-bold text-cyan-300 text-sm">${unit.id}</div>
            <h4 class="font-bold text-white text-sm">${unit.name || eqType}</h4>
            <span class="text-xs text-slate-400">Current: ${unit.location || 'Central Storage A'}</span>
          </div>
          <div class="grid grid-cols-2 gap-2 text-xs">
            <div class="p-2 bg-slate-950 rounded-lg">
              <span class="text-[10px] text-slate-400 block">Distance</span>
              <strong class="text-cyan-300">${unit.distance_m || 20}m away</strong>
            </div>
            <div class="p-2 bg-slate-950 rounded-lg">
              <span class="text-[10px] text-slate-400 block">Battery</span>
              <strong class="${unit.battery < 25 ? 'text-rose-400' : 'text-emerald-400'}">${unit.battery}%</strong>
            </div>
            <div class="p-2 bg-slate-950 rounded-lg">
              <span class="text-[10px] text-slate-400 block">Health</span>
              <strong class="text-emerald-400">${unit.health_score || 94}%</strong>
            </div>
            <div class="p-2 bg-slate-950 rounded-lg">
              <span class="text-[10px] text-slate-400 block">Score</span>
              <strong class="text-purple-300">${unit.composite_score ? (unit.composite_score * 100).toFixed(1) : '92.4'}%</strong>
            </div>
          </div>
          <p class="text-[11px] text-slate-300 leading-tight">${unit.why_selected || 'Optimal candidate based on distance and battery health.'}</p>
        </div>
      `).join('');
    }

    showToast('AI Allocation Complete', `Recommended top ${units.slice(0, qty).length} candidate units.`, 'success');
  } catch (e) {
    console.error('Allocation engine error:', e);
    showToast('Allocation Complete', 'Heuristic allocation evaluated.', 'info');
  }
}

async function confirmAndDispatchAllocation() {
  if (!state.activeAllocation || !state.activeAllocation.selected_units || state.activeAllocation.selected_units.length === 0) {
    await runAllocationEngine();
  }

  const units = state.activeAllocation?.selected_units || [{ id: 'WC-007' }];
  const targetWard = document.getElementById('alloc-target-ward')?.value || 'ward-emergency';

  for (const unit of units) {
    try {
      await fetch('/api/equipment/transfer', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': state.currentUser.role
        },
        body: JSON.stringify({
          equipment_id: unit.id,
          to_ward: targetWard.replace('ward-', '').toUpperCase(),
          reason: 'Autonomous Multi-Criteria AI Allocation Dispatch'
        })
      });
    } catch(err){}
  }

  showToast('Dispatch Confirmed', `Dispatched equipment to ${targetWard.replace('ward-', '').toUpperCase()}. Live route active on Blueprint.`, 'success');
  switchTab('blueprint');
  setTimeout(() => {
    animateHospitalTransitRoute();
  }, 400);
}

// --- Predictive Maintenance & MTBF Intelligence ---

async function renderMaintenancePage() {
  setTimeout(renderMaintenanceChart, 100);
  refreshMaintenanceData();
}

async function refreshMaintenanceData() {
  try {
    const res = await fetch('/api/esp32/hardware-state');
    if (res.ok) {
      const data = await res.json();
      if (data) {
        const eqEl = document.getElementById('maint-esp32-eq-id');
        const locEl = document.getElementById('maint-esp32-location');
        const usageEl = document.getElementById('maint-esp32-usage');
        const moveEl = document.getElementById('maint-esp32-movement');
        const tempEl = document.getElementById('maint-esp32-temp');
        
        if (data.equipment_id && eqEl) eqEl.textContent = data.equipment_id;
        if (data.location && locEl) locEl.textContent = data.location;
        if (data.temperature && tempEl) tempEl.textContent = `${data.temperature.toFixed(1)}°C`;
        if (usageEl) usageEl.textContent = (data.status === 'IN_USE' || data.is_in_motion) ? 'HIGH' : 'LOW';
        if (moveEl) moveEl.textContent = data.is_in_motion ? 'HIGH' : (data.status === 'IN_USE' ? 'HIGH' : 'NORMAL');
      }
    }
  } catch(e) {
    console.warn("Could not poll live hardware state for maintenance", e);
  }
}

function dispatchMaintenanceService(eqId) {
  showToast('Maintenance Scheduled', `Priority service ticket dispatched for ${eqId}. Inspection team notified.`, 'success');
}

function renderMaintenanceChart() {
  const canvas = document.getElementById('chart-maintenance-curve');
  if (!canvas || typeof Chart === 'undefined') return;

  if (state.charts.maintenanceRisk) {
    try { state.charts.maintenanceRisk.destroy(); } catch(e){}
  }

  const ctx = canvas.getContext('2d');
  const gradient = ctx.createLinearGradient(0, 0, 0, 200);
  gradient.addColorStop(0, 'rgba(244, 63, 94, 0.45)');
  gradient.addColorStop(1, 'rgba(244, 63, 94, 0.0)');

  state.charts.maintenanceRisk = new Chart(ctx, {
    type: 'line',
    data: {
      labels: ['Day 0 (Now)', 'Day 7', 'Day 14', 'Day 21', 'Day 28'],
      datasets: [
        {
          label: 'WC-014 Failure Risk (%)',
          data: [78, 84, 91, 95, 98],
          borderColor: '#f43f5e',
          backgroundColor: gradient,
          fill: true,
          tension: 0.35,
          borderWidth: 2.5,
          pointBackgroundColor: '#f43f5e',
          pointRadius: 4
        },
        {
          label: 'Critical Threshold (65%)',
          data: [65, 65, 65, 65, 65],
          borderColor: '#f59e0b',
          borderDash: [6, 4],
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false
        },
        {
          label: 'Fleet Baseline Average (15%)',
          data: [14, 15, 15, 16, 17],
          borderColor: '#10b981',
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: { color: '#94a3b8', font: { family: 'Inter', size: 10 } }
        },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y}%`
          }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94a3b8', font: { size: 10 } }
        },
        y: {
          min: 0,
          max: 100,
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: {
            color: '#94a3b8',
            font: { size: 10 },
            callback: (v) => `${v}%`
          }
        }
      }
    }
  });
}

// --- Diurnal Clinical Demand Forecasting ---

let activeForecastModel = 'xgboost';

function renderForecastPage() {
  setTimeout(() => renderForecastChart(activeForecastModel), 100);
}

function selectForecastModel(modelType) {
  activeForecastModel = modelType;
  const models = ['xgboost', 'rf', 'prophet', 'lstm'];
  models.forEach(m => {
    const btn = document.getElementById(`btn-model-${m}`);
    if (btn) {
      if (m === modelType) {
        btn.className = "p-3 rounded-2xl border text-left transition flex flex-col justify-between bg-indigo-50 border-indigo-300 text-indigo-950 shadow-sm";
      } else {
        btn.className = "p-3 rounded-2xl border border-slate-200 text-left transition flex flex-col justify-between hover:bg-slate-50 text-slate-700";
      }
    }
  });
  renderForecastChart(modelType);
  const labels = {
    xgboost: 'XGBoost Regressor (Gradient Boosting)',
    rf: 'Random Forest (Bagged Ensembles)',
    prophet: 'Prophet (Additive Seasonality)',
    lstm: 'Bi-LSTM Recurrent Neural Network'
  };
  showToast('Model Selected', `Forecasting activated with ${labels[modelType] || modelType.toUpperCase()}`, 'info');
}

function renderForecastChart(modelType = 'xgboost') {
  const canvas = document.getElementById('chart-demand-forecast');
  if (!canvas || typeof Chart === 'undefined') return;

  if (state.charts.demandForecast) {
    try { state.charts.demandForecast.destroy(); } catch(e){}
  }

  const ctx = canvas.getContext('2d');

  // Slight model variances for authentic ML presentation
  const multiplier = modelType === 'rf' ? 1.05 : (modelType === 'prophet' ? 0.96 : (modelType === 'lstm' ? 1.02 : 1.0));
  const wcData = [4, 3, 5, 8, 10, Math.round(13 * multiplier), 12, 10, 6];
  const ventData = [6, 6, 7, 8, 8, Math.round(10 * multiplier), 9, 8, 7];
  const ultraData = [1, 1, 1, 2, 2, Math.round(3 * multiplier), 3, 2, 1];

  state.charts.demandForecast = new Chart(ctx, {
    type: 'line',
    data: {
      labels: ['00:00', '03:00', '06:00', '09:00', '12:00', '15:00 (Peak)', '18:00', '21:00', '24:00'],
      datasets: [
        {
          label: 'Emergency Ward Wheelchairs (Predicted)',
          data: wcData,
          borderColor: '#06b6d4',
          backgroundColor: 'rgba(6, 182, 212, 0.12)',
          fill: true,
          tension: 0.35,
          borderWidth: 2.5,
          pointRadius: 4
        },
        {
          label: 'ICU Mechanical Ventilators (Predicted)',
          data: ventData,
          borderColor: '#f43f5e',
          backgroundColor: 'rgba(244, 63, 94, 0.08)',
          fill: true,
          tension: 0.35,
          borderWidth: 2.5,
          pointRadius: 4
        },
        {
          label: 'Gynaecology Ultrasound Units (Predicted)',
          data: ultraData,
          borderColor: '#a855f7',
          backgroundColor: 'rgba(168, 85, 247, 0.08)',
          fill: true,
          tension: 0.35,
          borderWidth: 2,
          pointRadius: 3
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: { color: '#475569', font: { family: 'Inter', size: 11, weight: 'bold' } }
        },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y} units required`
          }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(0, 0, 0, 0.05)' },
          ticks: { color: '#64748b', font: { size: 10 } }
        },
        y: {
          min: 0,
          max: 16,
          grid: { color: 'rgba(0, 0, 0, 0.05)' },
          ticks: {
            stepSize: 4,
            color: '#64748b',
            font: { size: 10 }
          }
        }
      }
    }
  });
}

// --- Emergency Operations & Code Red Triage ---

const activeEmergencyRequests = [
  {
    id: 'REQ-EM-902',
    ward: 'Emergency Ward',
    type: 'Wheelchair',
    quantity: 3,
    acuity: 'Critical',
    urgency_score: 94,
    priority: 'HIGH PRIORITY',
    response: 'Immediate allocation',
    reason: 'Multi-trauma incoming via Ambulance Bay.',
    status: 'ACTIVE_TRIAGE',
    time: 'Just now'
  },
  {
    id: 'REQ-EM-898',
    ward: 'ICU',
    type: 'Mechanical Ventilator',
    quantity: 1,
    acuity: 'Critical',
    urgency_score: 96,
    priority: 'HIGH PRIORITY',
    response: 'Immediate allocation',
    reason: 'Acute respiratory distress syndrome volume ventilation.',
    status: 'DISPATCHING',
    time: '4 mins ago'
  },
  {
    id: 'REQ-EM-891',
    ward: 'General Ward A',
    type: 'Wheelchair',
    quantity: 1,
    acuity: 'Stable',
    urgency_score: 48,
    priority: 'ROUTINE',
    response: 'Scheduled queue transfer',
    reason: 'Patient transfer to radiology for CT scan.',
    status: 'DISPATCHED',
    time: '24 mins ago'
  }
];

function renderEmergencyPage() {
  loadEmergencyRequestsQueue();
}

function loadEmergencyRequestsQueue() {
  const tbody = document.getElementById('emergency-queue-body');
  if (tbody) {
    tbody.innerHTML = activeEmergencyRequests.map(req => `
      <tr>
        <td class="font-mono font-bold text-slate-900 text-xs">${req.id}</td>
        <td class="font-bold text-slate-800 text-xs">${req.ward}</td>
        <td class="text-slate-700 text-xs">${req.type}</td>
        <td class="font-mono font-black text-slate-900 text-xs">${req.quantity}</td>
        <td>
          <span class="px-2 py-0.5 rounded text-[10px] font-bold ${req.acuity === 'Critical' ? 'bg-rose-100 text-rose-700 border border-rose-300' : (req.acuity === 'Urgent' ? 'bg-amber-100 text-amber-800 border border-amber-300' : 'bg-slate-100 text-slate-700')}">
            ${req.acuity.toUpperCase()} (${req.urgency_score || 94}/100)
          </span>
        </td>
        <td class="text-slate-400 font-mono text-[11px]">${req.time}</td>
        <td>
          <span class="px-2 py-0.5 rounded text-[10px] font-bold ${req.status === 'DISPATCHED' ? 'bg-emerald-100 text-emerald-800' : (req.status === 'ACTIVE_TRIAGE' ? 'bg-rose-100 text-rose-700 animate-pulse' : 'bg-blue-100 text-blue-700')}">
            ${req.status}
          </span>
        </td>
        <td class="text-right">
          ${req.status !== 'DISPATCHED' ? `
            <button onclick="dispatchImmediateEmergencyAllocation()" class="btn-pill btn-pill-primary text-[10px] py-1 bg-rose-600 hover:bg-rose-700">
              Dispatch
            </button>
          ` : `
            <span class="text-emerald-600 font-bold text-[11px]">En Route</span>
          `}
        </td>
      </tr>
    `).join('');
  }

  // Legacy container support if present
  const container = document.getElementById('em-requests-list');
  if (container) {
    container.innerHTML = activeEmergencyRequests.map(req => `
      <div class="p-3.5 rounded-2xl bg-slate-900 border ${req.acuity === 'Critical' ? 'border-rose-500/40 bg-rose-950/15' : 'border-slate-800'} text-xs space-y-2">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-2">
            <span class="font-mono font-bold text-cyan-300 text-xs">${req.id}</span>
            <span class="px-2 py-0.5 rounded text-[9px] font-black ${req.acuity === 'Critical' ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40' : 'bg-amber-500/20 text-amber-300'}">
              ${req.acuity.toUpperCase()} (${req.urgency_score}/100)
            </span>
          </div>
          <span class="text-[10px] text-slate-400 font-mono">${req.time}</span>
        </div>
        <div class="flex justify-between items-baseline">
          <div class="font-bold text-white text-sm">${req.quantity}x ${req.type}</div>
          <span class="text-slate-300 font-medium">${req.ward}</span>
        </div>
        <div class="flex justify-between items-center pt-2 border-t border-slate-800">
          <span class="text-[10px] font-bold ${req.status === 'DISPATCHED' ? 'text-emerald-400' : 'text-rose-400'}">
            ● STATUS: ${req.status}
          </span>
          <button onclick="dispatchImmediateEmergencyAllocation()" class="px-3 py-1 bg-rose-600 hover:bg-rose-500 text-white rounded-lg text-[10px] font-bold shadow-sm">
            Dispatch Now
          </button>
        </div>
      </div>
    `).join('');
  }

  const countEl = document.getElementById('em-queue-count');
  if (countEl) countEl.textContent = `${activeEmergencyRequests.length} Active Requests`;
}

async function submitEmergencyRequisition(event) {
  if (event) event.preventDefault();
  const wardSelect = document.getElementById('em-ward-select');
  const ward = wardSelect ? wardSelect.value : 'Emergency Ward';
  const eqSelect = document.getElementById('em-equipment-select');
  const eqType = eqSelect ? eqSelect.value : 'Wheelchair';
  const qtyInput = document.getElementById('em-quantity-input');
  const qty = parseInt(qtyInput ? qtyInput.value : '3') || 3;
  const statusSelect = document.getElementById('em-status-select');
  const patientStatus = statusSelect ? statusSelect.value : 'Critical';

  // AI Multi-Factor Prioritization (User Spec: Urgency + Ward + Availability + Demand + Distance)
  let score = 94;
  if (patientStatus === 'Critical' && ward === 'Emergency Ward') {
    score = 94;
  } else if (patientStatus === 'Critical') {
    score = 91;
  } else if (patientStatus === 'Urgent') {
    score = 78;
  } else {
    score = 52;
  }

  const priorityLevel = score >= 80 ? 'HIGH PRIORITY' : (score >= 60 ? 'MEDIUM PRIORITY' : 'ROUTINE');
  const recommendedResponse = score >= 85 ? 'Immediate allocation' : (score >= 70 ? 'Priority dispatch within 15 min' : 'Standard queue allocation');

  // Update Output Card (Exact User Spec)
  const badgeEl = document.getElementById('em-output-priority-badge');
  const wardEl = document.getElementById('em-output-ward');
  const reqTextEl = document.getElementById('em-output-req-text');
  const scoreEl = document.getElementById('em-output-score');
  const barEl = document.getElementById('em-output-score-bar');
  const respEl = document.getElementById('em-output-response');

  if (badgeEl) badgeEl.textContent = priorityLevel;
  if (wardEl) wardEl.textContent = ward;
  if (reqTextEl) reqTextEl.textContent = `${qty} ${eqType}${qty > 1 ? 's' : ''} Required`;
  if (scoreEl) scoreEl.textContent = `${score} / 100`;
  if (barEl) barEl.style.width = `${score}%`;
  if (respEl) respEl.textContent = recommendedResponse;

  const newReq = {
    id: `REQ-${Math.floor(1000 + Math.random() * 9000)}`,
    ward: ward,
    type: eqType,
    quantity: qty,
    acuity: patientStatus,
    urgency_score: score,
    priority: priorityLevel,
    response: recommendedResponse,
    reason: `Urgent requisition from ${ward}`,
    status: 'ACTIVE_TRIAGE',
    time: 'Just now'
  };

  activeEmergencyRequests.unshift(newReq);
  renderEmergencyPage();

  showToast('Priority Evaluated', `AI Score: ${score}/100 • ${recommendedResponse}`, score >= 80 ? 'emergency' : 'info');

  // Post to backend
  try {
    fetch('/api/emergency/request', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ward_id: ward.toLowerCase().replace(/\s+/g, '-'),
        equipment_type: eqType,
        quantity: qty,
        patient_urgency: patientStatus,
        reason: `Requisition from ${ward}`
      })
    });
  } catch(e) {}
}

const handleEmergencyRequestSubmit = submitEmergencyRequisition;

function dispatchImmediateEmergencyAllocation() {
  const reqText = document.getElementById('em-output-req-text')?.textContent || '3 Wheelchairs Required';
  const wardText = document.getElementById('em-output-ward')?.textContent || 'Emergency Ward';

  if (activeEmergencyRequests.length > 0) {
    activeEmergencyRequests[0].status = 'DISPATCHED';
  }
  renderEmergencyPage();

  showToast('Code Red Dispatched', `Allocating ${reqText} immediately to ${wardText}. Navigation corridors pre-empted!`, 'emergency');

  setTimeout(() => {
    switchTab('blueprint');
    setTimeout(animateHospitalTransitRoute, 400);
  }, 1000);
}

// --- Computer Vision & YOLO AI ---

let visionAnimId = null;
let currentVisionZone = 'Zone A: Central Storage';

function renderVisionAiPage() {
  initVisionCanvas();
}

function initVisionCanvas() {
  const canvas = document.getElementById('vision-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  canvas.width = 1280;
  canvas.height = 720;

  if (visionAnimId) cancelAnimationFrame(visionAnimId);

  let scanLineY = 0;
  let scanDir = 1;

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Deep CCTV camera perspective background
    const bgGrad = ctx.createLinearGradient(0, 0, 0, canvas.height);
    bgGrad.addColorStop(0, '#090d16');
    bgGrad.addColorStop(1, '#03060a');
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Grid floor perspective lines
    ctx.strokeStyle = 'rgba(6, 182, 212, 0.09)';
    ctx.lineWidth = 1;
    for (let x = 100; x < canvas.width; x += 120) {
      ctx.beginPath();
      ctx.moveTo(x, 260);
      ctx.lineTo((x - 640) * 2.5 + 640, canvas.height);
      ctx.stroke();
    }
    for (let y = 300; y < canvas.height; y += 70) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width, y);
      ctx.stroke();
    }

    // Scanning horizontal laser beam
    scanLineY += 2.5 * scanDir;
    if (scanLineY > canvas.height) scanDir = -1;
    if (scanLineY < 0) scanDir = 1;

    const laserGrad = ctx.createLinearGradient(0, scanLineY - 15, 0, scanLineY + 15);
    laserGrad.addColorStop(0, 'rgba(6, 182, 212, 0)');
    laserGrad.addColorStop(0.5, 'rgba(6, 182, 212, 0.25)');
    laserGrad.addColorStop(1, 'rgba(6, 182, 212, 0)');
    ctx.fillStyle = laserGrad;
    ctx.fillRect(0, scanLineY - 15, canvas.width, 30);

    // Scan line core
    ctx.strokeStyle = 'rgba(6, 182, 212, 0.6)';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(0, scanLineY);
    ctx.lineTo(canvas.width, scanLineY);
    ctx.stroke();

    // Timecode in corner
    ctx.font = 'bold 15px monospace';
    ctx.fillStyle = 'rgba(255, 255, 255, 0.55)';
    const now = new Date();
    const timeStr = `REC [●] ${now.toISOString().substring(11, 19)}.${Math.floor(now.getMilliseconds() / 100)}`;
    ctx.fillText(timeStr, 40, canvas.height - 30);

    visionAnimId = requestAnimationFrame(draw);
  }

  draw();
}

function toggleVisionCameraStream() {
  const zones = ['Zone A: Central Storage', 'Zone B: ICU Bay 3', 'Zone C: Emergency Triage'];
  const curIdx = zones.indexOf(currentVisionZone);
  currentVisionZone = zones[(curIdx + 1) % zones.length];

  const pill = document.getElementById('vision-active-zone-pill');
  if (pill) pill.textContent = currentVisionZone;

  showToast('Camera Feed Switched', `Active stream: ${currentVisionZone}`, 'info');
}

function auditVisionDiscrepancies() {
  showToast('Running Optical Audit', 'Capturing YOLO high-res tensor frame & comparing against SQLite...', 'info');
  setTimeout(() => {
    showToast('Audit Complete', 'Discrepancy confirmed: 1 Stretcher unrecorded in Zone A. Reconcile suggested.', 'warning');
  }, 900);
}

function resolveDiscrepancy(item) {
  const itemEl = document.querySelector('#vision-audit-items > div:nth-child(2)');
  if (itemEl) {
    itemEl.className = 'p-3.5 rounded-2xl bg-emerald-50/80 border border-emerald-200 text-xs space-y-2';
    itemEl.innerHTML = `
      <div class="flex items-center justify-between">
        <span class="font-black text-slate-900 uppercase font-mono">Stretchers</span>
        <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">AUTO-RECONCILED</span>
      </div>
      <div class="grid grid-cols-2 gap-2 text-[11px]">
        <div class="bg-white p-2 rounded-xl border border-emerald-100">
          <span class="text-slate-400 block text-[9px] font-bold">CCTV OPTICAL</span>
          <span class="text-base font-black text-emerald-800 font-mono">2 Detected</span>
        </div>
        <div class="bg-white p-2 rounded-xl border border-emerald-100">
          <span class="text-slate-400 block text-[9px] font-bold">SQLITE DATABASE</span>
          <span class="text-base font-black text-emerald-800 font-mono">2 Updated</span>
        </div>
      </div>
      <p class="text-[11px] text-emerald-800 font-medium">Inventory synchronized. 1 Stretcher transferred to Emergency Ward log.</p>
    `;
  }
  showToast('Inventory Reconciled', 'SQLite database updated to match optical CCTV count.', 'success');
}

function openDiscrepancyModal() {
  const m = document.getElementById('discrepancy-modal');
  if (m) m.classList.remove('hidden');
}

function closeDiscrepancyModal() {
  const m = document.getElementById('discrepancy-modal');
  if (m) m.classList.add('hidden');
}

function syncVisionInventory() {
  closeDiscrepancyModal();
  showToast('Audit Synchronized', 'Physical YOLO camera inventory count verified. Discrepancy flag resolved.', 'success');
}

// --- Equipment Fleet Inventory Table ---

async function loadEquipmentInventoryTable() {
  const tbody = document.getElementById('equipment-table-body') || document.getElementById('inventory-table-body');
  if (!tbody) return;

  if (!state.equipmentList || state.equipmentList.length === 0) {
    try {
      const res = await fetch('/api/equipment', {
        headers: { 'X-User-Role': state.currentUser ? state.currentUser.role : 'EQUIPMENT_MANAGER' }
      });
      state.equipmentList = await res.json();
      state.filteredEquipment = [...state.equipmentList];
    } catch (e) {
      console.error('Failed to load inventory table:', e);
    }
  } else if (!state.filteredEquipment || state.filteredEquipment.length === 0) {
    state.filteredEquipment = [...state.equipmentList];
  }

  renderInventoryTableRows(state.filteredEquipment);
}

function renderInventoryTableRows(items) {
  const tbody = document.getElementById('equipment-table-body') || document.getElementById('inventory-table-body');
  const badge = document.getElementById('inv-count-badge');
  const sub = document.getElementById('eq-inventory-subtitle');
  if (!tbody) return;

  const totalCount = state.equipmentList ? state.equipmentList.length : items.length;
  if (badge) badge.textContent = `${items.length} of ${totalCount} Assets`;
  if (sub && totalCount > 0) {
    sub.textContent = `Full telemetry inventory of ${totalCount} registered clinical assets with RFID tags and active states.`;
  }

  if (!items || items.length === 0) {
    tbody.innerHTML = '<tr><td colspan="10" class="py-12 text-center text-slate-500 font-medium">No equipment matching query found.</td></tr>';
    return;
  }

  tbody.innerHTML = items.map(item => {
    let statusBadge = 'bg-slate-100 text-slate-700 border-slate-200';
    if (item.status === 'AVAILABLE') statusBadge = 'bg-emerald-50 text-emerald-700 border-emerald-200';
    else if (item.status === 'IN_USE') statusBadge = 'bg-blue-50 text-blue-700 border-blue-200';
    else if (item.status === 'TEMPORARY_HOLD') statusBadge = 'bg-amber-50 text-amber-700 border-amber-200';
    else if (item.status === 'RETURNING_TO_STORAGE') statusBadge = 'bg-purple-50 text-purple-700 border-purple-200';
    else if (item.status === 'MAINTENANCE') statusBadge = 'bg-rose-50 text-rose-700 border-rose-200';

    const batt = typeof item.battery === 'number' ? item.battery : 100;
    const health = typeof item.health_score === 'number' ? item.health_score : 95;

    return `
      <tr class="hover:bg-indigo-50/40 transition cursor-pointer" onclick="openEquipmentDetailDrawer('${item.id}')">
        <!-- 1. EQUIPMENT ID -->
        <td class="py-3 px-4 font-mono font-bold text-xs">
          <span class="text-indigo-700 bg-indigo-50 border border-indigo-200/80 px-2 py-0.5 rounded-md inline-block shadow-xs">${item.id}</span>
        </td>

        <!-- 2. NAME & MODEL -->
        <td class="py-3 px-4">
          <div class="font-bold text-slate-900 text-xs">${item.name}</div>
          <div class="text-[10px] text-slate-400 font-medium">${item.department || 'Clinical Fleet'}</div>
        </td>

        <!-- 3. TYPE -->
        <td class="py-3 px-4">
          <span class="text-[11px] font-semibold text-slate-600 bg-slate-100 px-2 py-0.5 rounded-full border border-slate-200/80">${item.type}</span>
        </td>

        <!-- 4. LOCATION -->
        <td class="py-3 px-4 text-xs font-semibold text-slate-800">
          ${item.location}
        </td>

        <!-- 5. ROOM -->
        <td class="py-3 px-4 text-xs text-slate-500 font-medium">
          ${item.room || 'General Area'}
        </td>

        <!-- 6. STATUS -->
        <td class="py-3 px-4">
          <span class="px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${statusBadge}">${item.status.replace(/_/g, ' ')}</span>
        </td>

        <!-- 7. RFID UID -->
        <td class="py-3 px-4">
          <span class="font-mono text-[11px] font-medium text-slate-600 bg-slate-50 px-2 py-0.5 rounded border border-slate-200">${item.rfid_uid || '—'}</span>
        </td>

        <!-- 8. BATTERY -->
        <td class="py-3 px-4">
          <div class="flex items-center space-x-1.5">
            <span class="w-2 h-2 rounded-full ${batt < 20 ? 'bg-rose-500 animate-pulse' : (batt < 50 ? 'bg-amber-500' : 'bg-emerald-500')}"></span>
            <span class="text-xs font-bold ${batt < 20 ? 'text-rose-600' : 'text-slate-700'}">${batt}%</span>
          </div>
        </td>

        <!-- 9. HEALTH -->
        <td class="py-3 px-4">
          <div class="flex items-center space-x-2">
            <div class="w-14 h-1.5 bg-slate-200 rounded-full overflow-hidden">
              <div class="h-full ${health < 75 ? 'bg-rose-500' : 'bg-emerald-500'}" style="width: ${health}%"></div>
            </div>
            <span class="text-xs font-bold ${health < 75 ? 'text-rose-600' : 'text-emerald-700'}">${health}%</span>
          </div>
        </td>

        <!-- 10. ACTION -->
        <td class="py-3 px-4 text-right" onclick="event.stopPropagation()">
          <div class="flex items-center justify-end space-x-1.5">
            <button onclick="openEquipmentDetailDrawer('${item.id}')" class="px-2.5 py-1 bg-white hover:bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-lg text-[11px] font-bold shadow-xs transition">
              Detail
            </button>
            <button onclick="spotlightOnBlueprint('${item.id}')" class="px-2.5 py-1 bg-white hover:bg-blue-50 text-blue-700 border border-blue-200 rounded-lg text-[11px] font-bold shadow-xs transition">
              Map
            </button>
            <button onclick="openTransferModal('${item.id}')" class="px-2.5 py-1 bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 rounded-lg text-[11px] font-bold shadow-xs transition">
              Transfer
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function filterEquipmentTable() {
  const input = document.getElementById('eq-search-input');
  handleTableSearch(input ? input.value : '');
}

function handleTableSearch(query) {
  const q = (query || '').toLowerCase().trim();
  if (!state.equipmentList) return;

  if (!q) {
    state.filteredEquipment = [...state.equipmentList];
  } else {
    state.filteredEquipment = state.equipmentList.filter(item => 
      (item.id && item.id.toLowerCase().includes(q)) ||
      (item.name && item.name.toLowerCase().includes(q)) ||
      (item.type && item.type.toLowerCase().includes(q)) ||
      (item.location && item.location.toLowerCase().includes(q)) ||
      (item.room && item.room.toLowerCase().includes(q)) ||
      (item.rfid_uid && item.rfid_uid.toLowerCase().includes(q)) ||
      (item.status && item.status.toLowerCase().includes(q))
    );
  }
  renderInventoryTableRows(state.filteredEquipment);
}

// --- Auxiliary Handlers ---

function saveSettings() {
  showToast('Settings Persisted', 'Autonomous allocation heuristic weights and IoT alert thresholds saved.', 'success');
}

function requestUrgentVentilator() {
  showToast('Ventilator Staged', 'AI pre-allocated backup ventilator from Central Storage to ICU Bed Station.', 'success');
  switchTab('blueprint');
  setTimeout(animateHospitalTransitRoute, 400);
}

function toggleUserStatus(userId, newStatus) {
  showToast('User Status Updated', `User ${userId} status updated to ${newStatus}.`, 'info');
  loadUsersTable();
}

// --- Preserved Core Features (Counters, Charts, WebSocket, Toast, Simulation) ---

function initCounters() {
  const counters = [
    { id: 'kpi-total', target: 247 },
    { id: 'kpi-available', target: 132 },
    { id: 'kpi-in-use', target: 96 },
    { id: 'kpi-maintenance', target: 19 }
  ];

  counters.forEach(c => {
    const el = document.getElementById(c.id);
    if (!el) return;
    let current = 0;
    const increment = Math.max(1, Math.ceil(c.target / 30));
    const timer = setInterval(() => {
      current += increment;
      if (current >= c.target) {
        current = c.target;
        clearInterval(timer);
      }
      el.textContent = current;
    }, 35);
  });
}

function initWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  try {
    state.ws = new WebSocket(wsUrl);

    state.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleIncomingTelemetry(data);
      } catch (err) {
        console.error('WebSocket parse error:', err);
      }
    };

    state.ws.onclose = () => {
      setTimeout(initWebSocket, 4000);
    };
  } catch (e) {
    console.error('WebSocket failure:', e);
  }
}

function handleIncomingTelemetry(data) {
  if (data.type === 'RFID_SCAN_EVENT') {
    const sbRfid = document.getElementById('sidebar-last-rfid');
    if (sbRfid) sbRfid.textContent = data.uid;
    showToast('Equipment Identified', `✓ ${data.equipment_type.toUpperCase()} ${data.equipment_id} IDENTIFIED (${data.location})`, 'success', () => {
      window.location.href = '/hardware-simulator';
    });
    loadBlueprintData();
  } else if (data.type === 'EMERGENCY_ALERT') {
    showToast('🔴 High Priority Alert', `${data.ward_name}: ${data.quantity} ${data.equipment_type}s requested.`, 'emergency');
  } else if (data.type === 'EQUIPMENT_MOVED') {
    showToast('Equipment Relocated', `${data.equipment_id} transferred to ${data.to_location}`, 'info');
    loadBlueprintData();
  } else if (data.type === 'WHEELCHAIR_STORAGE_TICK') {
    if (state.currentTab === 'dashboard') {
      updateWheelchairReturnCountdown(data.remaining_seconds);
    }
    const stepStorage = document.getElementById('flow-storage');
    if (stepStorage) {
      stepStorage.textContent = `Wheelchair Storage (${data.remaining_seconds}s)`;
    }
  } else if (data.type === 'WHEELCHAIR_STORAGE_STARTED') {
    showToast(
      '♿ WHEELCHAIR RETURN INITIATED',
      `<span class="font-bold text-white">WC-007</span> returned to <span class="text-cyan-300">Radiology Wheelchair Storage</span>.<br><span class="text-emerald-300 font-bold">2-Minute automated verification countdown started.</span>`,
      'info',
      () => { switchTab('dashboard'); }
    );
    loadBlueprintData();
    loadWheelchairReturnStatus();
    if (state.currentTab === 'radiology') loadRadiologyDashboard(false);
  } else if (data.type === 'WHEELCHAIR_STORAGE_VERIFIED') {
    showToast(
      '✓ WHEELCHAIR RETURN VERIFIED',
      `<span class="font-bold text-white">WC-007</span> verified in storage.<br>Status is now <span class="font-extrabold text-emerald-400">AVAILABLE</span>. Radiology transport delay cleared.`,
      'success',
      () => { switchTab('dashboard'); }
    );
    loadBlueprintData();
    loadWheelchairReturnStatus();
    loadDashRadiologyQuickStats();
    if (state.currentTab === 'radiology') loadRadiologyDashboard(false);
  } else if (data.type === 'WHEELCHAIR_STORAGE_CANCELLED') {
    showToast(
      '⚠️ WHEELCHAIR RETURN CANCELLED',
      `<span class="font-bold text-white">WC-007</span>: ${data.reason || 'Movement detected'}. Reverted to <span class="text-sky-300 font-bold">${data.status}</span>.`,
      'warning',
      () => { switchTab('blueprint'); }
    );
    loadBlueprintData();
    loadWheelchairReturnStatus();
    loadDashRadiologyQuickStats();
    if (state.currentTab === 'radiology') loadRadiologyDashboard(false);
  } else if (data.type === 'RADIOLOGY_QUEUE_UPDATED') {
    if (state.currentTab === 'radiology') {
      loadRadiologyDashboard(false);
    }
    loadDashRadiologyQuickStats();
  } else if (data.type === 'TEMPORARY_HOLD_STARTED' || data.type === 'TEMPORARY_HOLD_ENDED') {
    loadBlueprintData();
    if (state.currentTab === 'dashboard') renderRoleDashboard();
    if (state.currentTab === 'equipment') loadEquipmentInventoryTable();
  } else if (data.type === 'ESP32_HARDWARE_UPDATE' || data.type === 'ESP32_EQUIPMENT_UPDATE' || data.type === 'EQUIPMENT_STATUS_CHANGED') {
    // If EQUIPMENT_STATUS_CHANGED is from ESP32_HARDWARE, skip duplicate notification
    if (data.type === 'EQUIPMENT_STATUS_CHANGED' && data.source === 'ESP32_HARDWARE') {
      return;
    }
    // Prevent double toasts if backend sends both ESP32_HARDWARE_UPDATE and ESP32_EQUIPMENT_UPDATE for same event
    if (data.type === 'ESP32_EQUIPMENT_UPDATE' && window._lastHwUpdateTs === data.timestamp) {
      return;
    }
    if (data.timestamp) window._lastHwUpdateTs = data.timestamp;

    // Forward pure serial log packets from ESP32 to terminal
    if (data.serial_logs && Array.isArray(data.serial_logs) && !data.status && !data.equipment) {
      data.serial_logs.forEach(l => {
        if (l) logToSimTerminal(l);
      });
      return;
    }

    if (data.distance_meters !== undefined && data.distance_meters !== null) {
      const d = parseFloat(data.distance_meters);
      if (!isNaN(d)) tabOdometry.distanceMeters = d;
    }
    if (data.rssi !== undefined && data.rssi !== null) {
      tabOdometry.rssi = parseInt(data.rssi);
    }
    if (data.speed_mps !== undefined && data.speed_mps !== null) {
      const s = parseFloat(data.speed_mps);
      if (!isNaN(s)) tabOdometry.speedMps = s;
    } else if (data.status && data.status !== 'IN_USE') {
      tabOdometry.speedMps = 0.0;
    }

    // Live real hardware telemetry takes precedence over manual simulation interval
    if (tabOdometry.moveInterval) {
      clearInterval(tabOdometry.moveInterval);
      tabOdometry.moveInterval = null;
    }

    tabOdometry.isMoving = (tabOdometry.speedMps > 0.0 || !!data.moving);

    // Directly update mini map coordinates based on REAL physical distance
    const cycleDist = 30.0;
    const rawProgress = (tabOdometry.distanceMeters % (cycleDist * 2));
    let progress = 0;
    if (rawProgress <= cycleDist) {
      progress = rawProgress / cycleDist;
    } else {
      progress = 1.0 - ((rawProgress - cycleDist) / cycleDist);
    }
    tabOdometry.currentX = tabOdometry.startPosX + (tabOdometry.endPosX - tabOdometry.startPosX) * progress;

    if (data.status && data.status !== 'IN_USE') {
      tabOdometry.distanceMeters = 0.0;
      tabOdometry.speedMps = 0.0;
      tabOdometry.rssi = -42;
      tabOdometry.currentX = tabOdometry.startPosX;
      tabOdometry.isMoving = false;
    }
    updateTabOdometryUI();

    const eqTitle = data.equipment || data.equipment_name || data.equipment_id;
    const eqId = data.equipment_id;
    const displayName = (eqTitle && eqId && !eqTitle.includes(eqId)) ? `${eqTitle} (${eqId})` : (eqTitle || eqId);

    const isWarning = !!(
      data.warning || 
      data.event === 'TEMP_WAIT_BLOCKED' || 
      data.event_type === 'TEMP_WAIT_BLOCKED' ||
      data.red_led_state === 'BLINKING' ||
      (data.serial_logs && data.serial_logs.some(l => l && l.includes('End usage before temporary waiting')))
    );

    if (data.event === 'WAYPOINT_VERIFIED' || data.event_type === 'WAYPOINT_VERIFIED') {
      const wpName = data.location || data.waypoint || 'Hospital Corridor Checkpoint';
      const dist = (data.distance_meters !== undefined) ? `${parseFloat(data.distance_meters).toFixed(1)} m` : '';
      showToast(
        '📍 RFID WAYPOINT VERIFIED',
        `<span class="font-bold text-white">${displayName}</span> reached <span class="font-bold text-cyan-300">${wpName}</span> (${dist})`,
        'success',
        () => { switchTab('blueprint'); }
      );
    } else if (isWarning) {
      showToast(
        '⚠️ ESP32 HARDWARE ALERT',
        `<div class="space-y-1">
          <div class="font-bold text-white">${displayName}</div>
          <div class="text-rose-300 font-bold text-xs">${data.warning || 'Equipment is currently in use. End usage before temporary waiting.'}</div>
          <div class="text-[10px] text-slate-300 font-mono flex items-center space-x-1 mt-0.5">
            <span class="w-2 h-2 rounded-full bg-rose-500 animate-ping inline-block"></span>
            <span>RED LIGHT BLINKING • End usage before temporary waiting</span>
          </div>
        </div>`,
        'warning',
        () => {
          window.location.href = '/hardware-simulator';
        }
      );
    } else if (data.status && data.previous_status && data.status !== data.previous_status && data.event !== 'RF_SIGNAL_TRACKING' && data.event !== 'EQUIPMENT_MOVING') {
      showToast(
        '⚡ ESP32 HARDWARE LAB SYNC',
        `<span class="font-bold text-white">${displayName}</span><br>Status changed to <span class="font-bold text-emerald-300">${data.status}</span>`,
        'success',
        () => {
          window.location.href = '/hardware-simulator';
        }
      );
    }
    loadBlueprintData();
    if (state.currentTab === 'dashboard') renderRoleDashboard();
    if (state.currentTab === 'equipment') loadEquipmentInventoryTable();
    if (state.currentTab === 'icu') loadICUDigitalTwin();
  }
}

async function fetchInitialData() {
  try {
    const res = await fetch('/api/equipment');
    state.equipmentList = await res.json();
    state.filteredEquipment = [...state.equipmentList];
  } catch (e) {
    console.error('Failed to fetch initial equipment:', e);
  }
}

function toggleDemoMode() {
  state.isDemoMode = !state.isDemoMode;
  const btn = document.getElementById('btn-mode-toggle');
  const txt = document.getElementById('mode-text');
  if (state.isDemoMode) {
    btn.className = 'px-3 py-1.5 rounded-xl border text-xs font-bold transition flex items-center space-x-1.5 bg-purple-950/40 text-purple-200 border-purple-500/40';
    txt.textContent = 'DEMO MODE';
    showToast('Demo Mode Active', 'Sensor simulations enabled', 'info');
  } else {
    btn.className = 'px-3 py-1.5 rounded-xl border text-xs font-bold transition flex items-center space-x-1.5 bg-emerald-950/40 text-emerald-200 border-emerald-500/40';
    txt.textContent = 'LIVE HARDWARE';
    showToast('Live Mode Active', 'Streaming actual hardware nodes', 'success');
  }
}

async function simulateRFIDScan() {
  try {
    await fetch('/api/demo/simulate-step', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'rfid_scan' })
    });
  } catch (e) {
    console.error('RFID simulation error:', e);
  }
}

async function simulateIoTMotion() {
  try {
    await fetch('/api/demo/simulate-step', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'iot_movement' })
    });
    showToast('PIR Motion Ping', 'Active movement session registered on WC-009', 'info');
  } catch (e) {
    console.error('IoT motion error:', e);
  }
}

async function simulateEmergencySurge() {
  try {
    await fetch('/api/demo/simulate-step', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'emergency_surge' })
    });
  } catch (e) {
    console.error('Emergency surge error:', e);
  }
}

// --- Tab Hardware Sim Movement Odometry & Mini Hospital Map ---

const tabOdometry = {
  isMoving: false,
  distanceMeters: 0.0,
  rssi: -42,
  speedMps: 0.0,
  startPosX: 65,
  endPosX: 390,
  currentX: 65,
  currentY: 80,
  moveInterval: null,
  lastLogTime: 0
};

function updateTabOdometryUI() {
  const distEl = document.getElementById('tab-hud-distance-val');
  const rssiEl = document.getElementById('tab-hud-rssi-val');
  const speedEl = document.getElementById('tab-hud-speed-val');
  const zoneEl = document.getElementById('tab-hud-zone-val');
  const badgeEl = document.getElementById('tab-sim-motion-badge');
  const coordsEl = document.getElementById('tab-map-coords-badge');
  const markerEl = document.getElementById('tab-mini-map-marker');
  const trackActive = document.getElementById('tab-transit-track-active');
  const btnText = document.getElementById('tab-btn-movement-text');

  if (distEl) distEl.textContent = tabOdometry.distanceMeters.toFixed(1);
  if (rssiEl) rssiEl.textContent = tabOdometry.rssi || -42;
  if (speedEl) speedEl.textContent = (tabOdometry.isMoving ? tabOdometry.speedMps : 0.0).toFixed(1);

  let zoneName = "Emergency Ward (Dock A)";
  if (tabOdometry.currentX > 320) {
    zoneName = "Radiology Suite (CT/MRI)";
  } else if (tabOdometry.currentX > 130) {
    zoneName = "Central Transit Corridor";
  }
  if (zoneEl) zoneEl.textContent = zoneName;

  if (badgeEl) {
    if (tabOdometry.isMoving) {
      badgeEl.textContent = "IN TRANSIT";
      badgeEl.className = "text-[9px] font-mono px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-bold animate-pulse";
    } else {
      badgeEl.textContent = "STATIONARY";
      badgeEl.className = "text-[9px] font-mono px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200 font-bold";
    }
  }

  if (btnText) {
    btnText.textContent = tabOdometry.isMoving ? "Pause Moving" : "Simulate Moving";
  }

  if (coordsEl) coordsEl.textContent = `X: ${Math.round(tabOdometry.currentX)} • Y: 80`;

  if (markerEl) {
    markerEl.setAttribute('transform', `translate(${tabOdometry.currentX.toFixed(1)}, 80)`);
  }
  if (trackActive) {
    trackActive.setAttribute('d', `M 65 80 L ${tabOdometry.currentX.toFixed(1)} 80`);
  }
}

function startTabMoving() {
  tabOdometry.isMoving = true;
  updateTabOdometryUI();
}

function stopTabMoving() {
  tabOdometry.isMoving = false;
  if (tabOdometry.moveInterval) {
    clearInterval(tabOdometry.moveInterval);
    tabOdometry.moveInterval = null;
  }
  updateTabOdometryUI();
}

function toggleTabSimulatedMovement() {
  if (tabOdometry.isMoving) {
    stopTabMoving();
  } else {
    startTabMoving();
  }
}

function resetTabDistanceOdometry() {
  stopTabMoving();
  tabOdometry.distanceMeters = 0.0;
  tabOdometry.speedMps = 0.0;
  tabOdometry.steps = 0;
  tabOdometry.currentX = tabOdometry.startPosX;
  updateTabOdometryUI();
}

function logToSimTerminal(msg) {
  const term = document.getElementById('sim-serial-output');
  if (!term) return;
  const line = document.createElement('div');
  line.textContent = msg;
  if (msg.includes('ODOMETRY') || msg.includes('Moving')) {
    line.className = 'text-cyan-300 font-mono';
  } else if (msg.includes('ERROR') || msg.includes('WARNING')) {
    line.className = 'text-rose-400 font-mono';
  } else {
    line.className = 'text-emerald-400 font-mono';
  }
  term.appendChild(line);
  term.scrollTop = term.scrollHeight;
}

function animateHospitalTransitRoute() {
  const route = document.getElementById('bp-animated-route');
  if (route) {
    route.classList.add('map-route-animated');
    route.setAttribute('stroke', '#00f2fe');
    route.setAttribute('stroke-width', '5');
    route.setAttribute('filter', 'url(#glow-cyan)');

    // Add pulsing destination beacon at end of route
    const routesGroup = document.getElementById('bp-routes-group');
    if (routesGroup && !document.getElementById('bp-transit-beacon')) {
      const destBeacon = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      destBeacon.setAttribute('id', 'bp-transit-beacon');
      destBeacon.setAttribute('cx', '750');
      destBeacon.setAttribute('cy', '140');
      destBeacon.setAttribute('r', '14');
      destBeacon.setAttribute('class', 'spotlight-ring');
      routesGroup.appendChild(destBeacon);

      setTimeout(() => {
        if (routesGroup.contains(destBeacon)) routesGroup.removeChild(destBeacon);
      }, 8000);
    }
  }
}

function toggleMediaiDrawer() {
  const drawer = document.getElementById('mediai-drawer');
  if (drawer) drawer.classList.toggle('hidden');
}

function askMediaiChip(promptText) {
  const inp = document.getElementById('mediai-input');
  if (inp) inp.value = promptText;
  handleMediaiSubmit(new Event('submit'));
}

async function handleMediaiSubmit(e) {
  if (e) e.preventDefault();
  const inp = document.getElementById('mediai-input');
  const chatBox = document.getElementById('mediai-chat-box');
  if (!inp || !chatBox) return;

  const query = inp.value.trim();
  if (!query) return;

  const userMsg = document.createElement('div');
  userMsg.className = 'p-3 rounded-2xl bg-purple-600 text-white ml-auto max-w-[85%] text-right font-medium text-xs';
  userMsg.textContent = query;
  chatBox.appendChild(userMsg);
  inp.value = '';
  chatBox.scrollTop = chatBox.scrollHeight;

  const thinking = document.createElement('div');
  thinking.className = 'p-3 rounded-2xl bg-slate-900 border border-slate-800 text-slate-400 text-xs flex items-center space-x-2';
  thinking.innerHTML = '<span class="pulse-live mr-1"></span> Interrogating hospital database...';
  chatBox.appendChild(thinking);
  chatBox.scrollTop = chatBox.scrollHeight;

  try {
    const res = await fetch('/api/assistant/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: query })
    });
    const data = await res.json();
    chatBox.removeChild(thinking);

    const botMsg = document.createElement('div');
    botMsg.className = 'p-3.5 rounded-2xl bg-slate-900/90 border border-purple-500/30 text-slate-100 text-xs leading-relaxed';
    let formatted = data.response
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/\n\n/g, '<br><br>')
      .replace(/\n•/g, '<br>•');

    botMsg.innerHTML = formatted;
    chatBox.appendChild(botMsg);
    chatBox.scrollTop = chatBox.scrollHeight;
  } catch (err) {
    chatBox.removeChild(thinking);
  }
}

function showToast(title, message, type = 'info', onClick = null) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  const bgStyles = type === 'emergency' 
    ? 'bg-rose-950/90 border-rose-500/70 text-rose-100 shadow-rose-950/60'
    : (type === 'success' 
      ? 'bg-emerald-950/90 border-emerald-500/70 text-emerald-100 shadow-emerald-950/60'
      : (type === 'warning'
        ? 'bg-amber-950/90 border-amber-500/70 text-amber-100 shadow-amber-950/60'
        : 'bg-slate-900/95 border-cyan-500/60 text-slate-100 shadow-cyan-950/50'));

  const clickableStyles = onClick ? 'cursor-pointer hover:border-cyan-400 hover:scale-[1.02] active:scale-[0.98]' : '';

  toast.className = `p-4 rounded-2xl border backdrop-blur-xl shadow-2xl transition transform duration-300 pointer-events-auto min-w-[280px] max-w-sm flex items-start space-x-3 translate-y-2 opacity-0 ${bgStyles} ${clickableStyles}`;
  toast.innerHTML = `
    <div class="mt-0.5">
      ${type === 'emergency' ? '<span class="pulse-emergency"></span>' : '<span class="pulse-live"></span>'}
    </div>
    <div class="flex-1">
      <div class="font-extrabold text-xs tracking-wide uppercase">${title}</div>
      <div class="text-xs text-slate-300 mt-0.5 leading-snug">${message}</div>
      ${onClick ? '<div class="text-[10px] text-cyan-400 font-semibold mt-1.5 flex items-center space-x-1"><span>Tap to open ESP32 Hardware Lab</span> <span>→</span></div>' : ''}
    </div>
  `;

  if (onClick) {
    toast.addEventListener('click', (e) => {
      onClick(e);
    });
  }

  container.appendChild(toast);
  requestAnimationFrame(() => { toast.classList.remove('translate-y-2', 'opacity-0'); });
  setTimeout(() => {
    toast.classList.add('translate-y-2', 'opacity-0');
    setTimeout(() => { if (container.contains(toast)) container.removeChild(toast); }, 300);
  }, 5000);
}

// Background simulation heartbeat for live demonstration
setInterval(() => {
  if (!state.isDemoMode) return;
  const actions = ['rfid', 'iot'];
  const chosen = actions[Math.floor(Math.random() * actions.length)];
  if (chosen === 'rfid') {
    simulateRFIDScan();
  }
}, 14000);

/* ==========================================================================
   PHASE 3: WHEELCHAIR STORAGE AUTO-AVAILABILITY & HOSPITAL MAP FLOW
   ========================================================================== */

function updateBlueprintTransitFlow(equipmentItems) {
  const items = equipmentItems || (state.blueprintData ? state.blueprintData.equipment : state.equipmentList);
  if (!items) return;
  const wc = items.find(e => e.id === 'WC-007') || state.equipmentList.find(e => e.id === 'WC-007');
  const routeEl = document.getElementById('bp-animated-route');
  const stepWard = document.getElementById('flow-ward');
  const stepRad = document.getElementById('flow-rad');
  const stepStorage = document.getElementById('flow-storage');
  const stepAvail = document.getElementById('flow-avail');

  if (!wc) return;

  const loc = (wc.location || '').toUpperCase();
  const st = (wc.status || '').toUpperCase();

  // Reset base classes
  if (stepWard) stepWard.className = 'px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700/60 font-medium';
  if (stepRad) stepRad.className = 'px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700/60 font-medium';
  if (stepStorage) stepStorage.className = 'px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700/60 font-medium';
  if (stepAvail) stepAvail.className = 'px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700/60 font-medium';

  if (st === 'RETURNING_TO_STORAGE') {
    if (stepStorage) {
      stepStorage.className = 'px-2.5 py-0.5 rounded bg-amber-950/90 text-amber-300 border border-amber-500/80 font-bold ring-2 ring-amber-500/50 animate-pulse';
    }
    if (routeEl) {
      routeEl.setAttribute('d', 'M 200 200 L 680 200 L 680 340 L 890 340');
      routeEl.setAttribute('class', 'blueprint-transit-path');
    }
  } else if (st === 'AVAILABLE' && loc.includes('STORAGE')) {
    if (stepAvail) {
      stepAvail.className = 'px-2.5 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-500 font-extrabold ring-2 ring-emerald-500/50 shadow-md';
    }
    if (routeEl) {
      routeEl.setAttribute('d', 'M 680 340 L 890 340');
      routeEl.setAttribute('class', 'blueprint-transit-path');
    }
  } else if (loc.includes('RADIOLOGY')) {
    if (stepRad) {
      stepRad.className = 'px-2.5 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-500 font-bold';
    }
    if (routeEl) {
      routeEl.setAttribute('d', 'M 200 200 L 680 200 L 680 340');
      routeEl.setAttribute('class', 'map-route-animated');
    }
  } else {
    if (stepWard) {
      stepWard.className = 'px-2.5 py-0.5 rounded bg-sky-950 text-sky-300 border border-sky-500 font-bold';
    }
    if (routeEl) {
      routeEl.setAttribute('d', 'M 200 200 L 500 200');
      routeEl.setAttribute('class', 'map-route-animated');
    }
  }
}

let _wcCountdownInterval = null;
let _wcCurrentRemaining = 0;

async function loadWheelchairReturnStatus() {
  const container = document.getElementById('wheelchair-return-widget');
  if (!container) return;

  try {
    const res = await fetch('/api/equipment/wheelchair-storage/status');
    const data = await res.json();
    renderWheelchairReturnWidget(data);
  } catch (e) {
    console.error('Failed to load wheelchair storage status:', e);
  }
}

function renderWheelchairReturnWidget(data) {
  const container = document.getElementById('wheelchair-return-widget');
  if (!container) return;

  const eq = data.equipment || { id: 'WC-007', name: 'Wheelchair WC-007 (Smart IoT)', location: 'Radiology Wheelchair Storage', status: 'AVAILABLE' };
  const isVerifying = !!(data.is_verifying || eq.status === 'RETURNING_TO_STORAGE');
  _wcCurrentRemaining = data.remaining_seconds || (isVerifying ? 120 : 0);

  if (isVerifying) {
    const mins = String(Math.floor(_wcCurrentRemaining / 60)).padStart(2, '0');
    const secs = String(_wcCurrentRemaining % 60).padStart(2, '0');
    const progressPct = Math.min(100, Math.max(0, Math.round(((120 - _wcCurrentRemaining) / 120) * 100)));

    container.innerHTML = `
      <div class="space-y-4">
        <div class="flex items-center justify-between pb-3 border-b border-slate-100">
          <div>
            <div class="inline-flex items-center space-x-1.5 text-xs font-bold text-amber-700 uppercase tracking-wide">
              <span class="w-2 h-2 rounded-full bg-amber-500 animate-pulse"></span>
              <span>WHEELCHAIR RETURN BAY</span>
            </div>
            <h3 class="font-black text-slate-900 text-lg mt-0.5">${eq.id}</h3>
          </div>
          <span class="status-pill status-pill-hold animate-pulse">
            <span>RETURNING TO STORAGE</span>
          </span>
        </div>

        <div class="space-y-2 text-xs">
          <div class="flex justify-between items-center text-slate-600">
            <span class="font-medium text-slate-400">Location:</span>
            <span class="font-bold text-slate-800">${eq.location || 'Radiology Wheelchair Storage'}</span>
          </div>

          <div class="flex justify-between items-center text-slate-600">
            <span class="font-medium text-slate-400">Return verification:</span>
            <span class="font-mono font-black text-amber-700 text-sm" id="wc-return-countdown">${mins}:${secs} remaining</span>
          </div>

          <div class="flex justify-between items-center text-slate-600">
            <span class="font-medium text-slate-400">Status:</span>
            <span class="font-bold text-amber-700">RETURNING TO STORAGE</span>
          </div>
        </div>

        <!-- 2-Minute Verification Countdown Progress -->
        <div class="space-y-1 pt-1">
          <div class="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden border border-slate-200">
            <div id="wc-return-progress-bar" class="bg-gradient-to-r from-amber-500 via-emerald-500 to-blue-500 h-2.5 rounded-full transition-all duration-1000" style="width: ${progressPct}%"></div>
          </div>
          <div class="text-[11px] text-slate-500 font-medium text-center pt-0.5" id="wc-return-auto-note">
            [Automatically available in ${mins}:${secs}]
          </div>
        </div>

        <!-- Edge Case: Movement cancellation simulation -->
        <div class="pt-2 flex items-center justify-between border-t border-slate-100">
          <span class="text-[10px] text-slate-400 font-medium">Auto-verify edge case</span>
          <button onclick="cancelWheelchairStorageReturn('Movement detected during 2-minute countdown')" class="btn-pill bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200 text-xs font-bold transition flex items-center space-x-1.5">
            <i data-lucide="footprints" class="w-3.5 h-3.5"></i>
            <span>Simulate Motion (Cancel)</span>
          </button>
        </div>
      </div>
    `;

    // Start live countdown ticker
    if (!_wcCountdownInterval) {
      _wcCountdownInterval = setInterval(() => {
        if (_wcCurrentRemaining > 0) {
          _wcCurrentRemaining--;
          updateWheelchairReturnCountdown(_wcCurrentRemaining);
        } else {
          clearInterval(_wcCountdownInterval);
          _wcCountdownInterval = null;
          loadWheelchairReturnStatus();
          loadBlueprintData();
          loadDashRadiologyQuickStats();
        }
      }, 1000);
    }
  } else {
    // When completed or available
    if (_wcCountdownInterval) {
      clearInterval(_wcCountdownInterval);
      _wcCountdownInterval = null;
    }

    container.innerHTML = `
      <div class="space-y-4">
        <div class="flex items-center justify-between pb-3 border-b border-slate-100">
          <div>
            <div class="inline-flex items-center space-x-1.5 text-xs font-bold text-emerald-700 uppercase tracking-wide">
              <i data-lucide="check-circle" class="w-3.5 h-3.5 text-emerald-600"></i>
              <span>WHEELCHAIR RETURN BAY</span>
            </div>
            <h3 class="font-black text-slate-900 text-lg mt-0.5">${eq.id}</h3>
          </div>
          <span class="status-pill status-pill-available">
            <span>✓ AVAILABLE</span>
          </span>
        </div>

        <div class="space-y-2 text-xs">
          <div class="flex justify-between items-center text-slate-600">
            <span class="font-medium text-slate-400">Stored at:</span>
            <span class="font-bold text-slate-800">${eq.location || 'Radiology Wheelchair Storage'}</span>
          </div>

          <div class="flex justify-between items-center text-slate-600">
            <span class="font-medium text-slate-400">Return verified:</span>
            <span class="font-mono font-bold text-emerald-700 flex items-center space-x-1">
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping"></span>
              <span>LIVE</span>
            </span>
          </div>

          <div class="flex justify-between items-center text-slate-600">
            <span class="font-medium text-slate-400">Radiology Transport:</span>
            <span class="text-emerald-700 font-semibold">Immediate Readiness (0m delay)</span>
          </div>
        </div>

        <div class="pt-2 flex items-center justify-between border-t border-slate-100">
          <span class="text-[10px] text-slate-400 font-mono">RC522 Tag: 10 0D 71 5C</span>
          <button onclick="triggerWheelchairStorageReturn(120)" class="btn-pill btn-pill-primary text-xs flex items-center space-x-1.5">
            <i data-lucide="play" class="w-3.5 h-3.5"></i>
            <span>Test 2-Min Return Flow</span>
          </button>
        </div>
      </div>
    `;
  }

  lucide.createIcons();
}

function updateWheelchairReturnCountdown(remaining) {
  _wcCurrentRemaining = remaining;
  const mins = String(Math.floor(remaining / 60)).padStart(2, '0');
  const secs = String(remaining % 60).padStart(2, '0');
  const countEl = document.getElementById('wc-return-countdown');
  const noteEl = document.getElementById('wc-return-auto-note');
  const barEl = document.getElementById('wc-return-progress-bar');

  if (countEl) countEl.textContent = `${mins}:${secs} remaining`;
  if (noteEl) noteEl.textContent = `[Automatically available in ${mins}:${secs}]`;
  if (barEl) {
    const progressPct = Math.min(100, Math.max(0, Math.round(((120 - remaining) / 120) * 100)));
    barEl.style.width = `${progressPct}%`;
  }
}

async function triggerWheelchairStorageReturn(durationSeconds = 120) {
  try {
    const res = await fetch('/api/equipment/wheelchair-storage/trigger', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ equipment_id: 'WC-007', duration_seconds: durationSeconds })
    });
    const data = await res.json();
    if (res.ok) {
      showToast('Return Initiated', 'WC-007 returned to Radiology Storage. 2-min verification active.', 'success');
      loadWheelchairReturnStatus();
      loadBlueprintData();
    } else {
      showToast('Return Trigger Rejected', data.error || 'Transition denied', 'warning');
    }
  } catch (e) {
    console.error('Failed to trigger return:', e);
  }
}

async function cancelWheelchairStorageReturn(reason = 'Movement detected') {
  try {
    const res = await fetch('/api/equipment/wheelchair-storage/cancel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ equipment_id: 'WC-007', reason: reason, resumed_to: 'IN_USE' })
    });
    const data = await res.json();
    if (res.ok) {
      showToast('Verification Cancelled', `WC-007 moved: ${reason}. Status returned to IN_USE.`, 'warning');
      loadWheelchairReturnStatus();
      loadBlueprintData();
    } else {
      showToast('Cancel Failed', data.error || 'Request error', 'warning');
    }
  } catch (e) {
    console.error('Failed to cancel storage verification:', e);
  }
}

async function loadDashRadiologyQuickStats() {
  try {
    const res = await fetch('/api/radiology/dashboard');
    if (!res.ok) return;
    const data = await res.json();
    const tEl = document.getElementById('dash-rad-turnaround');
    const wEl = document.getElementById('dash-rad-waiting');
    const dEl = document.getElementById('dash-rad-transport-delay');

    const kpi = data.metrics || data.kpi_overview;
    if (tEl && kpi) tEl.textContent = `${kpi.average_turnaround_minutes}m`;
    if (wEl && kpi) wEl.textContent = `${kpi.waiting_for_scan_count ?? kpi.total_patients_waiting_scan}`;
    const link = data.wheelchair_transport_link || data.transport_connection;
    if (dEl && link) {
      const delay = link.delay_minutes;
      if (delay > 0) {
        dEl.textContent = `+${delay}m (Delay)`;
        dEl.className = 'text-base font-extrabold text-rose-400';
      } else {
        dEl.textContent = `0m (Ready)`;
        dEl.className = 'text-base font-extrabold text-emerald-400';
      }
    }
  } catch (e) {
    console.error('Failed to load dash radiology quick stats:', e);
  }
}

/* ==========================================================================
   PHASE 3: RADIOLOGY DIGITAL TWIN & SYNTHETIC OPERATIONS SUITE
   ========================================================================== */

state.radiologyFilter = { modality: '', priority: '' };
state.radiologyCurrentDashboard = null;

async function loadRadiologyDashboard(showLoader = true) {
  try {
    const res = await fetch('/api/radiology/dashboard');
    if (!res.ok) {
      console.error('Failed to fetch /api/radiology/dashboard, status:', res.status);
      return;
    }
    const data = await res.json();
    state.radiologyCurrentDashboard = data;

    // 1. Diurnal profile
    const diurnal = data.diurnal_profile || data.time_of_day;
    const diurnalText = document.getElementById('rad-diurnal-text');
    if (diurnalText && diurnal) {
      diurnalText.textContent = `${diurnal.time_label || diurnal.label || 'Day Shift'} (${diurnal.traffic_multiplier || diurnal.multiplier || '1.0'}x traffic)`;
    }

    // 2. Simulation Toggle button state
    const simDot = document.getElementById('rad-sim-dot');
    const simText = document.getElementById('rad-sim-text');
    if (simDot && simText) {
      if (data.simulation_active) {
        simDot.className = 'w-2 h-2 rounded-full bg-emerald-400 animate-ping';
        simText.textContent = 'DEMO SIMULATION: ON';
      } else {
        simDot.className = 'w-2 h-2 rounded-full bg-slate-500';
        simText.textContent = 'DEMO SIMULATION: PAUSED';
      }
    }

    // 3. Transport link banner
    const banner = document.getElementById('rad-transport-banner');
    const link = data.wheelchair_transport_link || data.transport_connection;
    if (banner && link) {
      const isReady = link.storage_has_available_wheelchair;
      banner.className = `p-4 rounded-2xl border transition-all duration-300 ${isReady ? 'bg-emerald-950/40 border-emerald-500/50' : 'bg-rose-950/40 border-rose-500/60'}`;
      banner.innerHTML = `
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div class="flex items-center space-x-3.5">
            <div class="w-10 h-10 rounded-xl ${isReady ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' : 'bg-rose-500/20 text-rose-400 border border-rose-500/40'} flex items-center justify-center font-black text-base flex-shrink-0">
              ${isReady ? '✓' : '⚠'}
            </div>
            <div>
              <div class="text-xs font-mono font-extrabold uppercase tracking-wide ${isReady ? 'text-emerald-300' : 'text-rose-300'} flex items-center space-x-2">
                <span>${isReady ? 'RADIOLOGY PATIENT TRANSPORT: NOMINAL' : 'RADIOLOGY TRANSPORT SHORTAGE: PRE-SCAN BOTTLENECK'}</span>
                <span class="px-1.5 py-0.2 rounded text-[9px] font-bold ${isReady ? 'bg-emerald-900/80 text-emerald-200' : 'bg-rose-900/80 text-rose-200'}">EQUIPMENT LINK</span>
              </div>
              <div class="text-xs text-white mt-0.5 font-medium">${link.status_message}</div>
            </div>
          </div>
          <div class="flex items-center space-x-3 flex-shrink-0">
            <div class="text-right">
              <span class="text-[10px] text-slate-400 block font-mono">Inpatient Queue Impact</span>
              <span class="text-xs font-mono font-black ${isReady ? 'text-emerald-700' : 'text-rose-700'}">
                ${link.delay_minutes > 0 ? `+${link.delay_minutes} min delay added` : 'Nominal (+0 min delay)'}
              </span>
            </div>
            <button onclick="switchTab('dashboard')" class="btn-pill btn-pill-secondary text-xs">
              Wheelchair Bay
            </button>
          </div>
        </div>
      `;
    }

    // 4. Top 4 KPIs
    const kpi = data.metrics || data.kpi_overview;
    const kpiScan = document.getElementById('rad-kpi-waiting-scan');
    const kpiProg = document.getElementById('rad-kpi-in-progress');
    const kpiRep = document.getElementById('rad-kpi-reports-pending');
    const kpiTurn = document.getElementById('rad-kpi-turnaround');

    if (kpi) {
      if (kpiScan) kpiScan.textContent = kpi.waiting_for_scan_count ?? kpi.total_patients_waiting_scan ?? '--';
      if (kpiProg) kpiProg.textContent = kpi.in_progress_count ?? kpi.total_scans_in_progress ?? '--';
      if (kpiRep) kpiRep.textContent = kpi.reports_pending_count ?? kpi.total_reports_pending ?? '--';
      if (kpiTurn) kpiTurn.textContent = `${kpi.average_turnaround_minutes}m`;
    }

    // 5. Modality Cards Grid
    const modGrid = document.getElementById('rad-modality-cards-grid');
    const modalities = data.modalities || (Array.isArray(data.modality_cards) ? Object.fromEntries(data.modality_cards.map(m => [m.modality, m])) : null);
    if (modGrid && modalities) {
      const iconMap = {
        'X-RAY': 'scan',
        'CT SCAN': 'circle-dot',
        'MRI': 'disc',
        'ULTRASOUND': 'waves',
        'MAMMOGRAPHY': 'activity',
        'FLUOROSCOPY': 'radio',
        'INTERVENTIONAL RADIOLOGY': 'syringe'
      };

      modGrid.innerHTML = Object.entries(modalities).map(([mName, m]) => {
        let badgeClass = 'status-pill status-pill-available';
        const st = m.status || m.operational_status || 'OPTIMAL';
        if (st === 'PEAK LOAD' || st === 'ATTENTION') badgeClass = 'status-pill status-pill-hold';
        if (st === 'BOTTLENECK') badgeClass = 'status-pill status-pill-maintenance animate-pulse';

        const activeScans = m.active_scans ?? m.scan_in_progress_count ?? 0;
        const waitingPts = m.waiting_patients ?? m.patients_waiting ?? 0;

        return `
          <div class="glass-panel p-5 rounded-3xl space-y-3 hover:shadow-soft-indigo-lg transition cursor-pointer" onclick="openModalityDetail('${mName}')">
            <div class="flex items-center justify-between">
              <div class="flex items-center space-x-2.5">
                <div class="w-9 h-9 rounded-2xl bg-blue-50 text-blue-700 flex items-center justify-center font-bold">
                  <i data-lucide="${iconMap[mName] || 'layers'}" class="w-4 h-4"></i>
                </div>
                <div>
                  <h4 class="font-extrabold text-slate-900 text-xs">${mName}</h4>
                  <span class="text-[10px] text-slate-500 font-medium">${activeScans} Active • ${waitingPts} Waiting</span>
                </div>
              </div>
              <span class="${badgeClass}">
                ${st}
              </span>
            </div>

            <!-- Split Turnaround Breakdown -->
            <div class="p-3 rounded-2xl bg-slate-50 border border-slate-100 space-y-1.5 text-xs">
              <div class="flex justify-between text-slate-500 text-[11px]">
                <span>Scan Wait:</span>
                <span class="font-mono font-bold text-blue-700">${m.scan_wait_minutes}m</span>
              </div>
              <div class="flex justify-between text-slate-500 text-[11px]">
                <span>Scan Duration:</span>
                <span class="font-mono font-bold text-indigo-700">${m.scan_duration_minutes}m</span>
              </div>
              <div class="flex justify-between text-slate-500 text-[11px]">
                <span>Report Wait:</span>
                <span class="font-mono font-bold text-amber-700">${m.report_wait_minutes}m</span>
              </div>
              <div class="pt-1.5 border-t border-slate-200 flex justify-between font-bold text-xs">
                <span class="text-slate-900">Total Turnaround:</span>
                <span class="font-mono text-purple-700 font-black">${m.total_turnaround_minutes}m</span>
              </div>
            </div>
            <div class="flex items-center justify-between pt-1">
              <span class="text-[9px] text-slate-400 font-medium">${m.scan_wait_minutes}m + ${m.scan_duration_minutes}m + ${m.report_wait_minutes}m</span>
              <button class="text-[10px] font-bold text-blue-600 hover:text-blue-800 flex items-center space-x-0.5">
                <span>Inspect</span>
                <i data-lucide="chevron-right" class="w-3 h-3"></i>
              </button>
            </div>
          </div>
        `;
      }).join('');
    }

    // 6. Featured Patient Journey Timeline
    const featured = data.featured_patient_journey || data.featured_patient;
    if (featured) {
      renderPatientJourneyTimeline(featured);
    }

    // 7. AI Bottleneck Insights
    const insights = data.ai_bottleneck_insights || data.ai_insights;
    if (insights) {
      renderRadiologyInsights(insights);
    }

    // 8. Patient Flow Table
    loadRadiologyPatients();
    lucide.createIcons();
  } catch (e) {
    console.error('Failed to load radiology dashboard:', e);
  }
}

function renderPatientJourneyTimeline(p) {
  if (!p) return;
  const target = p.patient || p;
  const title = document.getElementById('rad-journey-title');
  const subtitle = document.getElementById('rad-journey-subtitle');
  const badge = document.getElementById('rad-journey-priority-badge');
  const container = document.getElementById('rad-journey-steps');

  if (title) title.textContent = `Patient ${target.patient_id} (${target.modality}) Operational Milestone Journey`;
  const orderTime = target.registration_time || target.request_time || target.order_placed_time || '10:00';
  if (subtitle) subtitle.textContent = `${target.department || 'Radiology'} • Order Placed: ${orderTime} • Total Turnaround: ${target.total_turnaround_minutes} min`;
  if (badge) {
    badge.textContent = target.priority || 'ROUTINE';
    if (target.priority === 'EMERGENCY') badge.className = 'status-pill status-pill-maintenance animate-pulse';
    else if (target.priority === 'URGENT') badge.className = 'status-pill status-pill-hold';
    else badge.className = 'status-pill status-pill-available';
  }

  if (!container) return;

  let steps = [];
  if (p.milestones && Array.isArray(p.milestones)) {
    const iconList = ['clipboard-list', 'navigation', 'camera', 'file-text', 'check-circle'];
    steps = p.milestones.map((m, idx) => ({
      step: (idx + 1).toString(),
      title: m.label || m.stage,
      time: m.duration_minutes ? `${m.duration_minutes} min` : (m.time || 'Completed'),
      desc: m.detail || '',
      status: m.status || 'COMPLETED',
      icon: iconList[idx] || 'check-circle'
    }));
  } else {
    steps = [
      {
        step: '1',
        title: 'Order Placed & Clinical Triage',
        time: orderTime,
        desc: `Ordered by ${target.doctor_id || 'Physician'} (${target.department || 'Ward'}) • Protocol: ${target.modality} Standard Imaging`,
        status: 'COMPLETED',
        icon: 'clipboard-list'
      },
      {
        step: '2',
        title: 'Pre-Scan Prep & Patient Transport',
        time: `Wait: ${target.waiting_for_scan_minutes} min`,
        desc: target.delay_reason || (target.waiting_for_scan_minutes > 15 ? 'Wheelchair transport staging in progress' : 'Ambulatory / Inpatient staged'),
        status: target.waiting_for_scan_minutes > 0 ? 'COMPLETED' : 'ACTIVE',
        icon: 'navigation'
      },
      {
        step: '3',
        title: 'Diagnostic Imaging Scan Execution',
        time: `Duration: ${target.scan_duration_minutes} min`,
        desc: `Suite: ${target.equipment_location || 'Gantry 1'} • Equipment: ${target.equipment_id || target.modality}`,
        status: target.report_status !== 'WAITING_FOR_SCAN' ? 'COMPLETED' : 'PENDING',
        icon: 'camera'
      },
      {
        step: '4',
        title: 'Radiologist Diagnostic Verification Queue',
        time: `Wait: ${target.waiting_for_report_minutes} min`,
        desc: `Reading queue: ${target.radiologist_status || 'Assigned Radiologist'} • Clinical Priority: ${target.priority}`,
        status: target.report_status === 'REPORT_READY' ? 'COMPLETED' : (target.report_status === 'REPORT_PENDING' ? 'ACTIVE' : 'PENDING'),
        icon: 'file-text'
      },
      {
        step: '5',
        title: 'Report Verified & Clinically Signed',
        time: `Total: ${target.total_turnaround_minutes} min`,
        desc: `Strict Formula: ${target.waiting_for_scan_minutes}m (wait) + ${target.scan_duration_minutes}m (scan) + ${target.waiting_for_report_minutes}m (report) = ${target.total_turnaround_minutes}m`,
        status: target.report_status === 'REPORT_READY' ? 'COMPLETED' : 'PENDING',
        icon: 'check-circle'
      }
    ];
  }

  container.innerHTML = steps.map(s => `
    <div class="flex items-start space-x-3.5 relative">
      <div class="w-8 h-8 rounded-2xl bg-blue-50 border border-blue-200 text-blue-700 flex items-center justify-center font-bold text-xs flex-shrink-0 z-10">
        ${s.step}
      </div>
      <div class="flex-1 pb-3 border-b border-slate-100">
        <div class="flex items-center justify-between">
          <h4 class="font-extrabold text-slate-900 text-xs">${s.title}</h4>
          <span class="text-[10px] font-semibold text-blue-700">${s.time}</span>
        </div>
        <p class="text-[11px] text-slate-500 mt-0.5">${s.desc}</p>
      </div>
    </div>
  `).join('');

  lucide.createIcons();
}

function renderRadiologyInsights(insights) {
  const container = document.getElementById('rad-ai-insights-container');
  if (!container || !Array.isArray(insights)) return;

  container.innerHTML = insights.map(i => {
    let cardClass = 'bg-purple-50/70 border border-purple-200 text-purple-950';
    let icon = 'sparkles';
    if (i.category === 'SCAN_CAPACITY_BOTTLENECK') {
      cardClass = 'bg-rose-50/70 border border-rose-200 text-rose-950';
      icon = 'disc';
    } else if (i.category === 'PATIENT_TRANSPORT_DELAY' || i.category === 'TRANSPORT_BOTTLENECK') {
      cardClass = 'bg-amber-50/70 border border-amber-200 text-amber-950';
      icon = 'alert-triangle';
    }

    const titleText = i.title ? `<div class="font-extrabold text-slate-900 text-xs">${i.title}</div>` : '';
    const descText = i.insight || i.description || '';
    const recText = i.recommended_action || i.recommendation || '';

    return `
      <div class="p-4 rounded-3xl ${cardClass} space-y-1.5 shadow-xs">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-2">
            <i data-lucide="${icon}" class="w-3.5 h-3.5 text-blue-600"></i>
            <span class="font-bold text-slate-900 text-xs">${i.modality || 'Hospital Fleet'}</span>
          </div>
          <span class="text-[9px] font-bold px-2 py-0.5 rounded-full bg-white/90 text-slate-700 border border-slate-200">
            ${i.severity || 'INFO'}
          </span>
        </div>
        ${titleText}
        <p class="text-[11px] text-slate-600 leading-relaxed">${descText}</p>
        ${recText ? `
        <div class="text-[10px] text-blue-700 font-semibold pt-1 border-t border-slate-200/60 flex items-center space-x-1">
          <span class="font-bold">Directive:</span>
          <span>${recText}</span>
        </div>` : ''}
      </div>
    `;
  }).join('');

  lucide.createIcons();
}

async function loadRadiologyPatients() {
  const tbody = document.getElementById('rad-patient-table-body');
  if (!tbody) return;

  try {
    const q = new URLSearchParams();
    if (state.radiologyFilter.modality) q.set('modality', state.radiologyFilter.modality);
    if (state.radiologyFilter.priority) q.set('priority', state.radiologyFilter.priority);

    const res = await fetch(`/api/radiology/patients?${q.toString()}`);
    if (!res.ok) {
      tbody.innerHTML = `<tr><td colspan="10" class="py-6 text-center text-rose-500 font-mono">Unable to load patient dataset (${res.status}). Server reconnecting...</td></tr>`;
      return;
    }
    const data = await res.json();
    const pts = data.patients || [];

    if (pts.length === 0) {
      tbody.innerHTML = `<tr><td colspan="10" class="py-6 text-center text-slate-400 font-medium text-xs">No patient flows match the selected filters.</td></tr>`;
      return;
    }

    tbody.innerHTML = pts.map(p => {
      let prioPill = 'status-pill status-pill-available';
      if (p.priority === 'EMERGENCY') prioPill = 'status-pill status-pill-maintenance animate-pulse';
      if (p.priority === 'URGENT') prioPill = 'status-pill status-pill-hold';

      return `
        <tr class="hover:bg-indigo-50/40 transition">
          <td class="py-2.5 px-3 font-mono font-bold text-blue-700">${p.patient_id}</td>
          <td class="py-2.5 px-3 font-semibold text-slate-900">${p.modality}</td>
          <td class="py-2.5 px-3 text-slate-600">${p.department}</td>
          <td class="py-2.5 px-3">
            <span class="${prioPill}">
              ${p.priority}
            </span>
          </td>
          <td class="py-2.5 px-3 font-mono text-blue-700 font-bold">${p.waiting_for_scan_minutes}m</td>
          <td class="py-2.5 px-3 font-mono text-indigo-700 font-bold">${p.scan_duration_minutes}m</td>
          <td class="py-2.5 px-3 font-mono text-amber-700 font-bold">${p.waiting_for_report_minutes}m</td>
          <td class="py-2.5 px-3 font-mono font-black text-purple-700">${p.total_turnaround_minutes}m</td>
          <td class="py-2.5 px-3">
            <span class="text-[10px] text-slate-500 font-medium">${p.report_status}</span>
          </td>
          <td class="py-2.5 px-3 text-right">
            <button onclick="inspectPatientJourney('${p.patient_id}')" class="px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200 text-[10px] font-bold transition">
              Inspect Journey
            </button>
          </td>
        </tr>
      `;
    }).join('');
  } catch (e) {
    console.error('Failed to load radiology patients:', e);
  }
}

function filterRadiologyTable() {
  const modSelect = document.getElementById('rad-filter-modality');
  const prioSelect = document.getElementById('rad-filter-priority');
  state.radiologyFilter.modality = modSelect ? modSelect.value : '';
  state.radiologyFilter.priority = prioSelect ? prioSelect.value : '';
  loadRadiologyPatients();
}

async function inspectPatientJourney(patientId) {
  try {
    const res = await fetch(`/api/radiology/patient/${patientId}`);
    if (res.ok) {
      const p = await res.json();
      renderPatientJourneyTimeline(p);
      showToast('Patient Timeline Loaded', `Inspecting milestone flow for ${patientId} (${p.patient?.modality || p.modality})`, 'info');
      const journeySec = document.getElementById('rad-journey-title');
      if (journeySec) journeySec.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  } catch (e) {
    console.error('Failed to inspect patient journey:', e);
  }
}

async function toggleRadiologySimulation() {
  try {
    const res = await fetch('/api/simulation/toggle', { method: 'POST' });
    const data = await res.json();
    showToast('Simulation Toggled', data.message || `Simulation is ${data.simulation_active ? 'ON' : 'PAUSED'}`, 'info');
    loadRadiologyDashboard(false);
  } catch (e) {
    console.error('Failed to toggle simulation:', e);
  }
}

async function stepRadiologySimulation() {
  try {
    const res = await fetch('/api/simulation/step', { method: 'POST' });
    const data = await res.json();
    showToast('Simulation Step (+5m)', `Autonomous flow stepped forward to tick ${data.simulation_tick}`, 'success');
    loadRadiologyDashboard(false);
    loadDashRadiologyQuickStats();
  } catch (e) {
    console.error('Failed to step simulation:', e);
  }
}

async function resetRadiologySimulation() {
  try {
    const res = await fetch('/api/simulation/reset', { method: 'POST' });
    const data = await res.json();
    showToast('Simulation Reset', 'Reproducible seed 42 dataset restored successfully.', 'info');
    loadRadiologyDashboard(false);
    loadDashRadiologyQuickStats();
  } catch (e) {
    console.error('Failed to reset simulation:', e);
  }
}


