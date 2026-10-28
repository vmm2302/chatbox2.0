import React, { useState, useEffect } from 'react';
import {
  Users,
  Database,
  Server,
  HardDrive,
  Cpu,
  Layers,
  UploadCloud,
  Trash2,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  FileText,
  Download,
  ShieldAlert,
  Activity,
  Terminal,
  Zap,
  Lock,
  Unlock,
  Shield,
  KeyRound,
  Search,
  Filter,
  X,
} from 'lucide-react';
import {
  getAdminMetrics,
  getAdminSources,
  uploadAdminFiles,
  clearAdminKnowledgeBase,
  getAdminTelemetry,
  getAdminOllama,
  getAdminAuditLogs,
  getAdminUserStats,
  getAdminUsers,
  updateAdminUserStatus,
  updateAdminUserRole,
  resetAdminUserPassword,
  deleteAdminUser,
} from '../services/api';

export default function AdminPanel({ currentUser }) {
  const [activeSubTab, setActiveSubTab] = useState('users'); // 'users' | 'kb' | 'telemetry' | 'audit'
  
  // Data states
  const [userStats, setUserStats] = useState({ total: 0, total_users: 0, active_admins: 0, active_count: 0 });
  const [usersList, setUsersList] = useState([]);
  const [userSearch, setUserSearch] = useState('');
  const [userRoleFilter, setUserRoleFilter] = useState('all');
  const [userStatusFilter, setUserStatusFilter] = useState('all');
  
  const [metrics, setMetrics] = useState(null);
  const [sources, setSources] = useState([]);
  const [telemetry, setTelemetry] = useState(null);
  const [ollama, setOllama] = useState(null);
  const [auditLogs, setAuditLogs] = useState([]);
  
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);

  // Ingestion form state
  const [uploadFiles, setUploadFiles] = useState([]);
  const [ingestMode, setIngestMode] = useState('merge'); // 'merge' | 'overwrite'
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  const addUploadFiles = (incoming) => {
    setUploadFiles((prev) => {
      const existingKeySet = new Set(prev.map(f => `${f.name}-${f.size}`));
      const newUnique = incoming.filter(f => !existingKeySet.has(`${f.name}-${f.size}`));
      return [...prev, ...newUnique];
    });
  };

  const removeUploadFile = (indexToRemove) => {
    setUploadFiles((prev) => prev.filter((_, idx) => idx !== indexToRemove));
  };

  const clearAllUploadFiles = () => {
    setUploadFiles([]);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFiles = Array.from(e.dataTransfer?.files || []);
    if (droppedFiles.length > 0) {
      addUploadFiles(droppedFiles);
    }
  };

  // Reset password modal state
  const [resetModalUser, setResetModalUser] = useState(null);
  const [newPasswordInput, setNewPasswordInput] = useState('');

  const adminUserId = currentUser?.id || 1;

  // Load all dashboard data safely
  const loadData = async () => {
    setLoading(true);
    try {
      const [uStats, uList, m, s, t, o, a] = await Promise.all([
        getAdminUserStats(adminUserId).catch(() => null),
        getAdminUsers(adminUserId, {
          search: userSearch,
          role: userRoleFilter,
          isActive: userStatusFilter === 'all' ? null : userStatusFilter === 'active',
        }).catch(() => []),
        getAdminMetrics(adminUserId).catch(() => null),
        getAdminSources(adminUserId).catch(() => []),
        getAdminTelemetry(adminUserId).catch(() => null),
        getAdminOllama(adminUserId).catch(() => null),
        getAdminAuditLogs(adminUserId, 50).catch(() => []),
      ]);

      if (uStats) setUserStats(uStats);
      if (Array.isArray(uList)) setUsersList(uList);
      if (m) setMetrics(m);
      if (Array.isArray(s)) setSources(s);
      else if (s && Array.isArray(s.sources)) setSources(s.sources);
      if (t) setTelemetry(t);
      if (o) setOllama(o);
      if (Array.isArray(a)) setAuditLogs(a);
      else if (a && Array.isArray(a.logs)) setAuditLogs(a.logs);
    } catch (err) {
      console.error('Failed to load admin data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [adminUserId, userRoleFilter, userStatusFilter]);

  // Handle user search on enter or debounce
  const handleSearchUsers = async (e) => {
    e.preventDefault();
    try {
      const uList = await getAdminUsers(adminUserId, {
        search: userSearch,
        role: userRoleFilter,
        isActive: userStatusFilter === 'all' ? null : userStatusFilter === 'active',
      });
      if (Array.isArray(uList)) setUsersList(uList);
    } catch (err) {
      console.error('Search error:', err);
    }
  };

  // User Actions: Lock/Unlock (Protected: Cannot lock Admin)
  const handleToggleUserStatus = async (user) => {
    if (user.role === 'admin') {
      window.alert('CẢNH BÁO BẢO VỆ: Không thể vô hiệu hóa tài khoản Quản trị viên (Admin).');
      return;
    }
    const nextStatus = !user.is_active;
    const confirmMsg = nextStatus
      ? `Bạn có chắc muốn mở khóa tài khoản '${user.username}'?`
      : `Bạn có chắc muốn KHÓA tài khoản '${user.username}'? Người này sẽ không thể đăng nhập tra từ được nữa.`;
    if (!window.confirm(confirmMsg)) return;

    try {
      await updateAdminUserStatus(adminUserId, user.id, nextStatus);
      setMessage({
        type: 'success',
        text: `Đã ${nextStatus ? 'mở khóa' : 'khóa'} tài khoản '${user.username}' thành công.`,
      });
      loadData();
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Lỗi cập nhật trạng thái.' });
    }
  };

  // User Actions: Delete User (Protected: Cannot delete Admin)
  const handleDeleteUser = async (user) => {
    if (user.role === 'admin') {
      window.alert('CẢNH BÁO BẢO VỆ: Tuyệt đối không thể xóa tài khoản Quản trị viên (Admin).');
      return;
    }
    const confirmMsg = `CẢNH BÁO NGUY HIỂM: Bạn có chắc chắn muốn XÓA VĨNH VIỄN tài khoản người dùng '${user.username}' (${user.display_name})?\n\nToàn bộ dữ liệu, nhật ký học tập và lịch sử tra cứu của người này sẽ bị xóa sạch và không thể hoàn tác!`;
    if (!window.confirm(confirmMsg)) return;

    try {
      await deleteAdminUser(adminUserId, user.id);
      setMessage({
        type: 'success',
        text: `Đã xóa vĩnh viễn tài khoản người dùng '${user.username}' thành công.`,
      });
      loadData();
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Lỗi khi xóa người dùng.' });
    }
  };

  // User Actions: Role Toggle
  const handleToggleUserRole = async (user) => {
    const nextRole = user.role === 'admin' ? 'user' : 'admin';
    const confirmMsg = nextRole === 'admin'
      ? `Nâng quyền tài khoản '${user.username}' thành Quản trị viên (Admin)?`
      : `Hạ quyền tài khoản '${user.username}' xuống Học viên thông thường?`;
    if (!window.confirm(confirmMsg)) return;

    try {
      await updateAdminUserRole(adminUserId, user.id, nextRole);
      setMessage({
        type: 'success',
        text: `Đã cập nhật vai trò của '${user.username}' thành ${nextRole.toUpperCase()}.`,
      });
      loadData();
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Lỗi cập nhật vai trò.' });
    }
  };

  // User Actions: Reset Password
  const handleExecuteResetPassword = async (e) => {
    e.preventDefault();
    if (!resetModalUser || !newPasswordInput || newPasswordInput.length < 6) {
      alert('Mật khẩu mới tối thiểu 6 ký tự.');
      return;
    }

    try {
      await resetAdminUserPassword(adminUserId, resetModalUser.id, newPasswordInput);
      setMessage({
        type: 'success',
        text: `Đã đặt lại mật khẩu mới cho tài khoản '${resetModalUser.username}' thành công.`,
      });
      setResetModalUser(null);
      setNewPasswordInput('');
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Lỗi đặt lại mật khẩu.' });
    }
  };

  // Handle file ingestion
  const handleUpload = async (e) => {
    e.preventDefault();
    if (!uploadFiles || uploadFiles.length === 0) return;

    setIsUploading(true);
    setMessage(null);

    try {
      const totalCount = uploadFiles.length;
      const res = await uploadAdminFiles(adminUserId, ingestMode, uploadFiles);
      const succ = res.success_count ?? totalCount;
      const skip = res.skipped_count ?? 0;
      const fail = res.failed_count ?? 0;
      const rec = res.ingested_records ?? 0;

      let msgText = `Nạp dữ liệu thành công! Đã xử lý ${rec} bản ghi từ ${totalCount} tệp (Thành công: ${succ}`;
      if (skip > 0) msgText += `, Bỏ qua trùng lặp: ${skip}`;
      if (fail > 0) msgText += `, Thất bại: ${fail}`;
      msgText += ').';

      setMessage({
        type: fail > 0 ? 'warning' : 'success',
        text: msgText,
      });
      setUploadFiles([]);
      await loadData();
    } catch (err) {
      setMessage({
        type: 'error',
        text: `Lỗi nạp dữ liệu: ${err.message}`,
      });
    } finally {
      setIsUploading(false);
    }
  };

  // Handle Clear KB
  const handleClearKB = async () => {
    const confirmed = window.confirm(
      'CẢNH BÁO QUAN TRỌNG: Hành động này sẽ xóa vĩnh viễn toàn bộ dữ liệu tri thức đã nạp, bao gồm tất cả các tệp tài liệu trong thư mục raw, toàn bộ vector ChromaDB, chỉ mục BM25 và bộ nhớ RAM. Bạn có chắc chắn muốn xóa sạch toàn bộ không?'
    );
    if (!confirmed) return;

    setLoading(true);
    try {
      await clearAdminKnowledgeBase(adminUserId);
      setMessage({
        type: 'success',
        text: 'Đã xóa và đặt lại toàn bộ cơ sở tri thức thành công!',
      });
      await loadData();
    } catch (err) {
      setMessage({
        type: 'error',
        text: `Lỗi xóa tri thức: ${err.message}`,
      });
    } finally {
      setLoading(false);
    }
  };

  // Export audit logs as JSON
  const handleExportAudit = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(auditLogs, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `audit_logs_${new Date().toISOString().slice(0, 10)}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  // Format helper for numbers
  const formatNum = (val, defaultVal = 0) => {
    const n = Number(val ?? defaultVal);
    return isNaN(n) ? String(defaultVal) : n.toLocaleString();
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      
      {/* Top Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white rounded-3xl p-6 sm:p-8 shadow-xl border border-slate-800 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-emerald-400 text-xs font-black uppercase tracking-widest mb-1">
            <ShieldAlert className="w-4 h-4" />
            <span>Hệ Thống Quản Trị Hệ Thống • Chatbox 2.0</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-black tracking-tight">
            Bảng Điều Khiển Quản Trị Viên (Admin Portal)
          </h1>
          <p className="text-xs sm:text-sm text-slate-300 mt-1 max-w-2xl">
            Quản trị toàn diện: Người dùng & phân quyền, nạp kho tri thức 4 tầng lưu trữ, giám sát tài nguyên phần cứng và Ollama LLM.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={loadData}
            disabled={loading}
            className="flex items-center space-x-1.5 px-4 py-2.5 rounded-xl bg-white/10 hover:bg-white/20 text-white text-xs font-bold border border-white/10 transition-all cursor-pointer"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Làm mới dữ liệu</span>
          </button>
        </div>
      </div>

      {/* Alert Notification Toast */}
      {message && (
        <div
          className={`flex items-center justify-between p-4 rounded-2xl border text-xs sm:text-sm font-semibold transition-all shadow-xs ${
            message.type === 'success'
              ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
              : 'bg-rose-50 text-rose-800 border-rose-200'
          }`}
        >
          <div className="flex items-center space-x-2.5">
            {message.type === 'success' ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
            ) : (
              <XCircle className="w-5 h-5 text-rose-600 shrink-0" />
            )}
            <span>{message.text}</span>
          </div>
          <button
            onClick={() => setMessage(null)}
            className="text-xs font-bold underline cursor-pointer hover:opacity-80 ml-4 shrink-0"
          >
            Đóng
          </button>
        </div>
      )}

      {/* Sub-Tabs Navigation (4 Modules Migrated from app.py) */}
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 pb-3">
        <button
          onClick={() => setActiveSubTab('users')}
          className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-bold transition-all cursor-pointer ${
            activeSubTab === 'users'
              ? 'bg-slate-900 text-white shadow-md'
              : 'bg-white text-slate-600 hover:text-slate-900 border border-slate-200'
          }`}
        >
          <Users className="w-4 h-4 text-cyan-400" />
          <span>👥 Quản lý Người dùng & Tài khoản</span>
        </button>

        <button
          onClick={() => setActiveSubTab('kb')}
          className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-bold transition-all cursor-pointer ${
            activeSubTab === 'kb'
              ? 'bg-slate-900 text-white shadow-md'
              : 'bg-white text-slate-600 hover:text-slate-900 border border-slate-200'
          }`}
        >
          <Database className="w-4 h-4 text-emerald-400" />
          <span>🗄️ Quản lý Tri thức (Knowledge Base)</span>
        </button>

        <button
          onClick={() => setActiveSubTab('telemetry')}
          className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-bold transition-all cursor-pointer ${
            activeSubTab === 'telemetry'
              ? 'bg-slate-900 text-white shadow-md'
              : 'bg-white text-slate-600 hover:text-slate-900 border border-slate-200'
          }`}
        >
          <Activity className="w-4 h-4 text-teal-400" />
          <span>📈 Chẩn đoán & Telemetry</span>
        </button>

        <button
          onClick={() => setActiveSubTab('audit')}
          className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-bold transition-all cursor-pointer ${
            activeSubTab === 'audit'
              ? 'bg-slate-900 text-white shadow-md'
              : 'bg-white text-slate-600 hover:text-slate-900 border border-slate-200'
          }`}
        >
          <Terminal className="w-4 h-4 text-amber-400" />
          <span>📜 Nhật ký Kiểm toán (Audit Logs)</span>
        </button>
      </div>

      {/* ======================================================== */}
      {/* MODULE 1: USER & ACCOUNT MANAGEMENT                       */}
      {/* ======================================================== */}
      {activeSubTab === 'users' && (
        <div className="space-y-6 animate-in fade-in duration-150">
          
          {/* User Metrics Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-bold uppercase tracking-wider">Tổng Số Tài Khoản</span>
                <div className="p-2 rounded-xl bg-blue-50 text-blue-600">
                  <Users className="w-4 h-4" />
                </div>
              </div>
              <div className="text-3xl font-black text-slate-900">
                {formatNum(userStats?.total)}
              </div>
              <p className="text-xs text-slate-500 mt-1">Bao gồm toàn bộ học viên và admin</p>
            </div>

            <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-bold uppercase tracking-wider">Học Viên Hoạt Động</span>
                <div className="p-2 rounded-xl bg-emerald-50 text-emerald-600">
                  <CheckCircle2 className="w-4 h-4" />
                </div>
              </div>
              <div className="text-3xl font-black text-emerald-700">
                {formatNum(userStats?.total_users)}
              </div>
              <p className="text-xs text-slate-500 mt-1">Được phép đăng nhập & tra từ</p>
            </div>

            <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-bold uppercase tracking-wider">Quản Trị Viên (Admin)</span>
                <div className="p-2 rounded-xl bg-indigo-50 text-indigo-600">
                  <Shield className="w-4 h-4" />
                </div>
              </div>
              <div className="text-3xl font-black text-indigo-700">
                {formatNum(userStats?.active_admins)}
              </div>
              <p className="text-xs text-slate-500 mt-1">Có toàn quyền quản trị hệ thống</p>
            </div>
          </div>

          {/* User Search & Filters */}
          <div className="bg-white rounded-3xl p-5 border border-slate-200 shadow-sm space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-base font-black text-slate-900 flex items-center space-x-2">
                <Search className="w-4 h-4 text-emerald-600" />
                <span>Danh Sách Tài Khoản Hệ Thống ({usersList.length})</span>
              </h2>

              <form onSubmit={handleSearchUsers} className="flex flex-wrap items-center gap-2">
                <div className="relative">
                  <input
                    type="text"
                    value={userSearch}
                    onChange={(e) => setUserSearch(e.target.value)}
                    placeholder="Tìm username hoặc tên hiển thị..."
                    className="py-1.5 pl-8 pr-3 text-xs bg-slate-50 rounded-xl border border-slate-200 text-slate-800 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/20"
                  />
                  <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
                </div>

                <select
                  value={userRoleFilter}
                  onChange={(e) => setUserRoleFilter(e.target.value)}
                  className="py-1.5 px-3 text-xs bg-slate-50 rounded-xl border border-slate-200 text-slate-700 font-medium focus:outline-hidden"
                >
                  <option value="all">Tất cả vai trò</option>
                  <option value="user">Chỉ Học viên (User)</option>
                  <option value="admin">Chỉ Quản trị viên (Admin)</option>
                </select>

                <select
                  value={userStatusFilter}
                  onChange={(e) => setUserStatusFilter(e.target.value)}
                  className="py-1.5 px-3 text-xs bg-slate-50 rounded-xl border border-slate-200 text-slate-700 font-medium focus:outline-hidden"
                >
                  <option value="all">Tất cả trạng thái</option>
                  <option value="active">Đang hoạt động</option>
                  <option value="disabled">Đã khóa</option>
                </select>

                <button
                  type="submit"
                  className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold transition-all cursor-pointer"
                >
                  Tìm
                </button>
              </form>
            </div>

            {/* User Data Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase font-black">
                  <tr>
                    <th className="py-3 px-3">ID</th>
                    <th className="py-3 px-4">Tài Khoản</th>
                    <th className="py-3 px-4">Tên Hiển Thị</th>
                    <th className="py-3 px-3">Vai Trò</th>
                    <th className="py-3 px-3">Trạng Thái</th>
                    <th className="py-3 px-4">Ngày Tạo</th>
                    <th className="py-3 px-4">Đăng Nhập Gần Nhất</th>
                    <th className="py-3 px-3 text-right">Thao Tác Quản Trị</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {usersList.length === 0 ? (
                    <tr>
                      <td colSpan="8" className="text-center py-8 text-slate-400">
                        Không tìm thấy người dùng nào phù hợp với bộ lọc.
                      </td>
                    </tr>
                  ) : (
                    usersList.map((u) => {
                      const isSelf = u.id === currentUser?.id;
                      const isAdmin = u.role === 'admin';
                      return (
                        <tr key={u.id} className="hover:bg-slate-50/80 transition-colors">
                          <td className="py-3 px-3 font-mono text-slate-400">#{u.id}</td>
                          <td className="py-3 px-4 font-bold text-slate-900 flex items-center space-x-2">
                            <div className={`w-6 h-6 rounded-lg text-white font-black text-[10px] flex items-center justify-center shrink-0 ${
                              isAdmin ? 'bg-indigo-600' : 'bg-emerald-600'
                            }`}>
                              {u.username.slice(0, 1).toUpperCase()}
                            </div>
                            <span>{u.username}</span>
                            {isSelf && (
                              <span className="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.2 rounded font-bold">
                                Bạn
                              </span>
                            )}
                          </td>
                          <td className="py-3 px-4 text-slate-700">{u.display_name || u.username}</td>
                          <td className="py-3 px-3">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-extrabold ${
                              isAdmin
                                ? 'bg-indigo-100 text-indigo-800 border border-indigo-200'
                                : 'bg-slate-100 text-slate-700 border border-slate-200'
                            }`}>
                              {isAdmin ? '🛡️ ADMIN' : '👤 USER'}
                            </span>
                          </td>
                          <td className="py-3 px-3">
                            <span className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[11px] font-bold ${
                              u.is_active
                                ? 'bg-emerald-100 text-emerald-800'
                                : 'bg-rose-100 text-rose-800'
                            }`}>
                              <span className={`w-1.5 h-1.5 rounded-full ${u.is_active ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                              <span>{u.is_active ? 'Hoạt động' : 'Đã khóa'}</span>
                            </span>
                          </td>
                          <td className="py-3 px-4 text-slate-500 font-mono text-[11px]">
                            {u.created_at ? u.created_at.slice(0, 10) : '-'}
                          </td>
                          <td className="py-3 px-4 text-slate-500 font-mono text-[11px]">
                            {u.last_login_at ? u.last_login_at.slice(0, 16).replace('T', ' ') : 'Chưa từng'}
                          </td>
                          <td className="py-3 px-3 text-right">
                            <div className="flex items-center justify-end space-x-1.5">
                              {/* Toggle active / lock */}
                              <button
                                onClick={() => handleToggleUserStatus(u)}
                                disabled={isSelf || isAdmin}
                                title={
                                  isAdmin
                                    ? 'Tài khoản Quản trị viên được bảo vệ (không thể khóa)'
                                    : isSelf
                                    ? 'Không thể tự khóa tài khoản của mình'
                                    : u.is_active
                                    ? 'Khóa tài khoản người dùng'
                                    : 'Mở khóa tài khoản người dùng'
                                }
                                className={`p-1.5 rounded-lg border transition-colors cursor-pointer ${
                                  isAdmin
                                    ? 'border-slate-200 text-slate-300 opacity-40 cursor-not-allowed'
                                    : u.is_active
                                    ? 'border-slate-200 text-slate-500 hover:text-rose-600 hover:bg-rose-50'
                                    : 'border-emerald-300 text-emerald-600 bg-emerald-50 hover:bg-emerald-100'
                                } disabled:opacity-30 disabled:cursor-not-allowed`}
                              >
                                {u.is_active ? <Lock className="w-3.5 h-3.5" /> : <Unlock className="w-3.5 h-3.5" />}
                              </button>

                              {/* Toggle role */}
                              <button
                                onClick={() => handleToggleUserRole(u)}
                                disabled={isSelf}
                                title={isAdmin ? 'Hạ quyền xuống User' : 'Nâng quyền lên Admin'}
                                className="p-1.5 rounded-lg border border-slate-200 text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 transition-colors cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                              >
                                <Shield className="w-3.5 h-3.5" />
                              </button>

                              {/* Reset password */}
                              <button
                                onClick={() => {
                                  setResetModalUser(u);
                                  setNewPasswordInput('');
                                }}
                                title="Đặt lại mật khẩu"
                                className="p-1.5 rounded-lg border border-slate-200 text-slate-500 hover:text-amber-600 hover:bg-amber-50 transition-colors cursor-pointer"
                              >
                                <KeyRound className="w-3.5 h-3.5" />
                              </button>

                              {/* Delete user account (Protected: Cannot delete Admin) */}
                              <button
                                onClick={() => handleDeleteUser(u)}
                                disabled={isSelf || isAdmin}
                                title={
                                  isAdmin
                                    ? 'Tài khoản Quản trị viên được bảo vệ (không thể xóa)'
                                    : isSelf
                                    ? 'Không thể tự xóa tài khoản của chính mình'
                                    : `Xóa vĩnh viễn tài khoản người dùng '${u.username}'`
                                }
                                className={`p-1.5 rounded-lg border transition-colors cursor-pointer ${
                                  isAdmin
                                    ? 'border-slate-200 text-slate-300 opacity-40 cursor-not-allowed'
                                    : 'border-slate-200 text-slate-500 hover:text-rose-600 hover:bg-rose-50 hover:border-rose-300'
                                } disabled:opacity-30 disabled:cursor-not-allowed`}
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Reset Password Modal */}
          {resetModalUser && (
            <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs z-50 flex items-center justify-center p-4">
              <div className="bg-white rounded-3xl p-6 max-w-md w-full shadow-2xl border border-slate-200 space-y-4 animate-in fade-in zoom-in-95 duration-150">
                <div className="flex items-center space-x-2 text-indigo-600">
                  <KeyRound className="w-5 h-5" />
                  <h3 className="text-base font-black text-slate-900">
                    Đặt Lại Mật Khẩu Người Dùng
                  </h3>
                </div>
                <p className="text-xs text-slate-600">
                  Nhập mật khẩu mới cho tài khoản: <b className="text-slate-900 font-extrabold">{resetModalUser.username}</b> ({resetModalUser.display_name}).
                </p>

                <form onSubmit={handleExecuteResetPassword} className="space-y-3">
                  <div>
                    <label className="text-xs font-bold text-slate-700 block mb-1">Mật khẩu mới (Tối thiểu 6 ký tự):</label>
                    <input
                      type="password"
                      required
                      value={newPasswordInput}
                      onChange={(e) => setNewPasswordInput(e.target.value)}
                      placeholder="Nhập mật khẩu mới..."
                      className="w-full py-2 px-3 text-sm rounded-xl border border-slate-300 focus:outline-hidden focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
                    />
                  </div>

                  <div className="flex items-center justify-end space-x-2 pt-2">
                    <button
                      type="button"
                      onClick={() => setResetModalUser(null)}
                      className="px-4 py-2 text-xs font-bold text-slate-600 hover:bg-slate-100 rounded-xl transition-colors cursor-pointer"
                    >
                      Hủy bỏ
                    </button>
                    <button
                      type="submit"
                      className="px-4 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow-md transition-all cursor-pointer"
                    >
                      Xác nhận đổi mật khẩu
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

        </div>
      )}

      {/* ======================================================== */}
      {/* MODULE 2: KNOWLEDGE BASE MANAGEMENT                       */}
      {/* ======================================================== */}
      {activeSubTab === 'kb' && (
        <div className="space-y-6 animate-in fade-in duration-150">
          
          {/* 4 Storage Layer Metrics Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            
            {/* Card 1: JSONL Records */}
            <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs hover:border-emerald-300 transition-all">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-bold uppercase tracking-wider">Tệp JSONL Gốc</span>
                <div className="p-2 rounded-xl bg-emerald-50 text-emerald-600">
                  <FileText className="w-4 h-4" />
                </div>
              </div>
              <div className="text-3xl font-black text-slate-900">
                {formatNum(metrics?.jsonl_disk_count ?? metrics?.layers?.jsonl_records, 10031)}
              </div>
              <p className="text-xs text-slate-500 mt-1">Bản ghi từ vựng lưu trữ vĩnh viễn trên đĩa</p>
            </div>

            {/* Card 2: RAM Cache */}
            <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs hover:border-teal-300 transition-all">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-bold uppercase tracking-wider">Bộ Nhớ Đệm RAM</span>
                <div className="p-2 rounded-xl bg-teal-50 text-teal-600">
                  <Zap className="w-4 h-4" />
                </div>
              </div>
              <div className="text-3xl font-black text-slate-900">
                {formatNum(metrics?.engine_records_count ?? metrics?.layers?.ram_cache_count, 10031)}
              </div>
              <p className="text-xs text-teal-600 font-semibold mt-1">Mục từ sẵn sàng truy vấn tức thì 0-latency</p>
            </div>

            {/* Card 3: ChromaDB Vectors */}
            <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs hover:border-indigo-300 transition-all">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-bold uppercase tracking-wider">ChromaDB Vectors</span>
                <div className="p-2 rounded-xl bg-indigo-50 text-indigo-600">
                  <Layers className="w-4 h-4" />
                </div>
              </div>
              <div className="text-3xl font-black text-slate-900">
                {formatNum(metrics?.chroma_count ?? metrics?.layers?.chroma_vectors, 128)}
              </div>
              <p className="text-xs text-slate-500 mt-1">Vectors ngữ nghĩa (Semantic search)</p>
            </div>

            {/* Card 4: BM25 Index */}
            <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs hover:border-amber-300 transition-all">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-bold uppercase tracking-wider">BM25 Lexical Index</span>
                <div className="p-2 rounded-xl bg-amber-50 text-amber-600">
                  <HardDrive className="w-4 h-4" />
                </div>
              </div>
              <div className="text-3xl font-black text-slate-900">
                {formatNum(metrics?.bm25_count ?? metrics?.layers?.bm25_documents, 10031)}
              </div>
              <p className="text-xs text-slate-500 mt-1">Chỉ mục từ khóa tìm kiếm chính xác</p>
            </div>

          </div>

          {/* Ingestion & Upload Section */}
          <div className="bg-white rounded-3xl p-6 sm:p-7 border border-slate-200 shadow-sm space-y-5">
            <div>
              <h2 className="text-lg font-black text-slate-900 flex items-center space-x-2">
                <UploadCloud className="w-5 h-5 text-emerald-600" />
                <span>Nạp Dữ liệu Tri thức Mới (Multi-format Ingestion)</span>
              </h2>
              <p className="text-xs text-slate-500 mt-1">
                Hỗ trợ 8 định dạng: <span className="font-semibold text-slate-700">.xlsx, .xls, .docx, .doc, .pdf, .csv, .tsv, .sqlite, .db</span>. Tự động đồng bộ vào 4 tầng lưu trữ.
              </p>
            </div>

            <form onSubmit={handleUpload} className="space-y-4">
              <div className="flex flex-wrap items-center gap-4">
                <span className="text-xs font-bold text-slate-700">Chế độ nạp:</span>
                <label className="flex items-center space-x-2 text-xs font-medium cursor-pointer">
                  <input
                    type="radio"
                    name="mode"
                    value="merge"
                    checked={ingestMode === 'merge'}
                    onChange={() => setIngestMode('merge')}
                    className="text-emerald-600 focus:ring-emerald-500"
                  />
                  <span>Hợp nhất (Merge - Giữ dữ liệu hiện có)</span>
                </label>

                <label className="flex items-center space-x-2 text-xs font-medium cursor-pointer">
                  <input
                    type="radio"
                    name="mode"
                    value="overwrite"
                    checked={ingestMode === 'overwrite'}
                    onChange={() => setIngestMode('overwrite')}
                    className="text-emerald-600 focus:ring-emerald-500"
                  />
                  <span>Ghi đè (Overwrite - Thay thế dữ liệu trùng lặp)</span>
                </label>
              </div>

              {/* File picker drop area */}
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`border-2 border-dashed rounded-2xl p-6 text-center transition-all ${
                  isDragging
                    ? 'border-emerald-500 bg-emerald-50/60 scale-[1.01]'
                    : 'border-slate-300 hover:border-emerald-500 bg-slate-50/50'
                }`}
              >
                <input
                  type="file"
                  multiple
                  accept=".xlsx,.xls,.docx,.doc,.pdf,.csv,.tsv,.sqlite,.db"
                  id="admin-file-input"
                  onChange={(e) => {
                    if (e.target.files) {
                      addUploadFiles(Array.from(e.target.files));
                    }
                    e.target.value = '';
                  }}
                  className="hidden"
                />
                <label htmlFor="admin-file-input" className="cursor-pointer space-y-2 block">
                  <UploadCloud className={`w-8 h-8 mx-auto transition-colors ${isDragging ? 'text-emerald-600' : 'text-slate-400'}`} />
                  <div className="text-sm font-bold text-slate-800">
                    Kéo thả nhiều tệp vào đây hoặc nhấp để chọn tệp tài liệu
                  </div>
                  <div className="text-xs text-slate-500">
                    Đã chọn: <span className="font-bold text-emerald-600">{uploadFiles.length}</span> tệp
                    {uploadFiles.length > 0 && ` (~${Math.round(uploadFiles.reduce((acc, f) => acc + f.size, 0) / 1024)} KB)`}
                  </div>
                </label>

                {uploadFiles.length > 0 && (
                  <div className="mt-4 space-y-2">
                    <div className="flex items-center justify-between px-1">
                      <span className="text-[11px] font-bold text-slate-600">
                        Danh sách tệp chờ nạp ({uploadFiles.length}):
                      </span>
                      <button
                        type="button"
                        onClick={clearAllUploadFiles}
                        className="text-[11px] font-semibold text-rose-600 hover:text-rose-700 underline cursor-pointer"
                      >
                        Xóa tất cả
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-2 justify-center max-h-36 overflow-y-auto p-1">
                      {uploadFiles.map((f, i) => (
                        <span
                          key={`${f.name}-${f.size}-${i}`}
                          className="inline-flex items-center space-x-1.5 text-[11px] bg-white border border-slate-200 pl-2.5 pr-1.5 py-1 rounded-lg text-slate-700 font-medium shadow-xs"
                        >
                          <span>📄 {f.name} ({Math.round(f.size / 1024)} KB)</span>
                          <button
                            type="button"
                            onClick={(ev) => {
                              ev.stopPropagation();
                              removeUploadFile(i);
                            }}
                            className="p-0.5 hover:bg-slate-100 rounded text-slate-400 hover:text-rose-500 cursor-pointer"
                            title="Xóa tệp này khỏi danh sách chờ"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={uploadFiles.length === 0 || isUploading}
                  className="flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white font-bold text-xs shadow-md shadow-emerald-500/20 disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer"
                >
                  <RefreshCw className={`w-4 h-4 ${isUploading ? 'animate-spin' : ''}`} />
                  <span>{isUploading ? 'Đang trích xuất & nạp tri thức...' : 'Bắt đầu nạp vào hệ thống'}</span>
                </button>
              </div>
            </form>
          </div>

          {/* Active Knowledge Sources Table */}
          <div className="bg-white rounded-3xl p-6 sm:p-7 border border-slate-200 shadow-sm space-y-4">
            <h2 className="text-lg font-black text-slate-900 flex items-center space-x-2">
              <HardDrive className="w-5 h-5 text-indigo-600" />
              <span>Danh sách Nguồn Tài liệu Đang Hoạt động ({sources.length})</span>
            </h2>

            {sources.length === 0 ? (
              <div className="text-center py-8 text-xs text-slate-400">
                Chưa có tệp nạp bổ sung nào. Cơ sở tri thức đang sử dụng bộ dữ liệu Oxford 3,000 mặc định.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase font-black">
                    <tr>
                      <th className="py-3 px-4">Tên Nguồn Dữ Liệu</th>
                      <th className="py-3 px-4">Định Dạng</th>
                      <th className="py-3 px-4">Số Bản Ghi</th>
                      <th className="py-3 px-4">Thời Gian Nạp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {sources.map((src, idx) => (
                      <tr key={idx} className="hover:bg-slate-50/80">
                        <td className="py-3 px-4 font-bold text-slate-800">📄 {src.filename || src.name}</td>
                        <td className="py-3 px-4">
                          <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-mono text-[10px]">
                            {src.format || 'CORPUS'}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-semibold text-emerald-700">{src.record_count || src.count || 0}</td>
                        <td className="py-3 px-4 text-slate-500">{src.ingested_at || 'Mặc định'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Danger Zone: Clear KB */}
          <div className="bg-rose-50/50 rounded-3xl p-6 border border-rose-200/80 flex flex-wrap items-center justify-between gap-4">
            <div>
              <h3 className="text-base font-black text-rose-900 flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 text-rose-600" />
                <span>Khu vực Cảnh báo Nguy hiểm (Danger Zone)</span>
              </h3>
              <p className="text-xs text-rose-700 mt-1 max-w-xl">
                Xóa sạch các chỉ mục ChromaDB, BM25 và hoàn nguyên bộ nhớ về trạng thái ban đầu.
              </p>
            </div>
            <button
              onClick={handleClearKB}
              className="flex items-center space-x-1.5 px-4 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-black text-xs shadow-md shadow-rose-600/20 transition-all cursor-pointer"
            >
              <Trash2 className="w-4 h-4" />
              <span>Xóa Toàn Bộ Tri Thức</span>
            </button>
          </div>

        </div>
      )}

      {/* ======================================================== */}
      {/* MODULE 3: TELEMETRY & SYSTEM DIAGNOSTICS                 */}
      {/* ======================================================== */}
      {activeSubTab === 'telemetry' && (
        <div className="space-y-6 animate-in fade-in duration-150">
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            
            {/* Hardware Resources */}
            <div className="bg-white rounded-3xl p-6 border border-slate-200 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-black text-slate-900 flex items-center space-x-2">
                  <Cpu className="w-5 h-5 text-teal-600" />
                  <span>Tài Nguyên Phần Cứng Máy Chủ</span>
                </h2>
                {telemetry?.resource_state && (
                  <span className="px-2.5 py-0.5 rounded-full text-[11px] font-black bg-emerald-100 text-emerald-800 border border-emerald-200">
                    🟢 {telemetry.resource_state}
                  </span>
                )}
              </div>

              <div className="space-y-4 text-xs">
                {/* RAM Gauge */}
                <div>
                  <div className="flex justify-between font-bold text-slate-700 mb-1">
                    <span>Bộ nhớ RAM Hệ thống:</span>
                    <span>
                      {telemetry?.ram_used_gb || roundGB(telemetry?.ram?.used_mb)} GB / {telemetry?.ram_total_gb || roundGB(telemetry?.ram?.total_mb)} GB ({telemetry?.ram_percent || telemetry?.ram?.load_pct || 0}%)
                    </span>
                  </div>
                  <div className="w-full bg-slate-100 rounded-full h-3 overflow-hidden">
                    <div
                      className={`h-full transition-all duration-500 ${
                        (telemetry?.ram_percent || telemetry?.ram?.load_pct || 0) > 85
                          ? 'bg-rose-500'
                          : (telemetry?.ram_percent || telemetry?.ram?.load_pct || 0) > 65
                          ? 'bg-amber-500'
                          : 'bg-emerald-500'
                      }`}
                      style={{ width: `${Math.min(telemetry?.ram_percent || telemetry?.ram?.load_pct || 15, 100)}%` }}
                    />
                  </div>
                </div>

                {/* VRAM / GPU Info */}
                <div className="bg-slate-50 p-3.5 rounded-2xl border border-slate-100 space-y-1.5">
                  <div className="font-bold text-slate-800 flex items-center space-x-1.5">
                    <Zap className="w-3.5 h-3.5 text-amber-500" />
                    <span>Card Đồ Họa & VRAM (GPU):</span>
                  </div>
                  <p className="text-slate-600">
                    Thiết bị: <b className="text-slate-900">{telemetry?.gpu_name || telemetry?.vram?.device_name || 'NVIDIA GeForce / CPU Fallback'}</b>
                  </p>
                  <p className="text-slate-600">
                    VRAM sử dụng: <b className="text-emerald-700">{telemetry?.vram_used_gb || roundGB(telemetry?.vram?.used_mb)} GB</b> / {telemetry?.vram_total_gb || 'Tự động cấp phát'}
                  </p>
                </div>

                {/* CPU Threading */}
                <div className="bg-slate-50 p-3.5 rounded-2xl border border-slate-100">
                  <div className="font-bold text-slate-800">Số luồng xử lý CPU (Workers):</div>
                  <div className="text-slate-600 mt-0.5">
                    Khả dụng: <b className="text-slate-900">{telemetry?.cpu_threads || telemetry?.cpu?.active_threads || 8} threads</b> • PyTorch & Uvicorn Async Pool
                  </div>
                </div>
              </div>
            </div>

            {/* Ollama LLM Service */}
            <div className="bg-white rounded-3xl p-6 border border-slate-200 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-black text-slate-900 flex items-center space-x-2">
                  <Server className="w-5 h-5 text-indigo-600" />
                  <span>Dịch Vụ Mô Hình Ngôn Ngữ Ollama</span>
                </h2>
                <span
                  className={`inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold ${
                    ollama?.online
                      ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                      : 'bg-amber-100 text-amber-800 border border-amber-200'
                  }`}
                >
                  <span
                    className={`w-2 h-2 rounded-full ${
                      ollama?.online ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'
                    }`}
                  />
                  <span>{ollama?.online ? 'Online (Cổng 11434)' : 'Offline (Direct Cache Fallback)'}</span>
                </span>
              </div>

              <div className="text-xs space-y-3">
                <p className="text-slate-600">
                  Mô hình cấu hình chính: <b className="text-indigo-700 font-mono font-bold">{ollama?.configured_model || 'qwen2.5:7b-instruct-q4_K_M'}</b>
                </p>

                <div>
                  <div className="font-bold text-slate-700 mb-1.5">Mô hình đã cài đặt (Local Models):</div>
                  {ollama?.installed_models && ollama.installed_models.length > 0 ? (
                    <div className="space-y-1.5 max-h-48 overflow-y-auto">
                      {ollama.installed_models.map((m, idx) => (
                        <div
                          key={idx}
                          className="flex items-center justify-between p-2 rounded-xl bg-slate-50 border border-slate-100 font-mono text-[11px]"
                        >
                          <span className="font-bold text-slate-800">{typeof m === 'string' ? m : m.name}</span>
                          <span className="text-slate-500 text-[10px]">Ready</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-3 bg-slate-50 rounded-xl text-slate-500 text-center">
                      Mô hình chính: <span className="font-bold text-slate-800">qwen2.5:7b-instruct-q4_K_M</span>
                    </div>
                  )}
                </div>

                <div className="p-3 rounded-xl bg-teal-50 border border-teal-100 text-teal-800 text-[11px]">
                  💡 <b>Fast Path:</b> Nếu Ollama đang bận hoặc offline, hệ thống tự động tra cứu từ điển RAM 10,031 mục từ mà không gây gián đoạn cho học viên.
                </div>
              </div>
            </div>

          </div>

        </div>
      )}

      {/* ======================================================== */}
      {/* MODULE 4: AUDIT LOGS                                      */}
      {/* ======================================================== */}
      {activeSubTab === 'audit' && (
        <div className="bg-white rounded-3xl p-6 sm:p-7 border border-slate-200 shadow-sm space-y-4 animate-in fade-in duration-150">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-black text-slate-900 flex items-center space-x-2">
                <Terminal className="w-5 h-5 text-amber-600" />
                <span>Nhật Ký Kiểm Toán Hoạt Động (Audit Trail)</span>
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Ghi nhận chi tiết các thao tác đăng nhập, nạp tệp, tra cứu, quản lý tài khoản và bảo mật.
              </p>
            </div>

            <button
              onClick={handleExportAudit}
              className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-all cursor-pointer"
            >
              <Download className="w-4 h-4" />
              <span>Xuất Tệp JSON</span>
            </button>
          </div>

          <div className="overflow-x-auto max-h-[500px]">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase font-black sticky top-0">
                <tr>
                  <th className="py-2.5 px-3">Thời Gian</th>
                  <th className="py-2.5 px-3">Người Dùng</th>
                  <th className="py-2.5 px-3">Hành Động</th>
                  <th className="py-2.5 px-3">Đối Tượng</th>
                  <th className="py-2.5 px-3">Trạng Thái</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-[11px]">
                {auditLogs.length === 0 ? (
                  <tr>
                    <td colSpan="5" className="text-center py-8 text-slate-400">
                      Chưa có sự kiện kiểm toán nào được ghi lại.
                    </td>
                  </tr>
                ) : (
                  auditLogs.map((log, idx) => (
                    <tr key={idx} className="hover:bg-slate-50">
                      <td className="py-2 px-3 text-slate-500">{log.timestamp || log.created_at || 'Vừa xong'}</td>
                      <td className="py-2 px-3 font-bold text-slate-800">{log.user_id || log.username || log.actor_username || 'System'}</td>
                      <td className="py-2 px-3">
                        <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-800 font-bold">
                          {log.action || log.event_type}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-slate-600 truncate max-w-xs">{log.target || log.details ? (typeof log.details === 'object' ? JSON.stringify(log.details) : log.details) : '-'}</td>
                      <td className="py-2 px-3">
                        <span
                          className={`px-1.5 py-0.5 rounded font-bold ${
                            log.status === 'success' || log.status === 'SUCCESS' || !log.status
                              ? 'bg-emerald-100 text-emerald-800'
                              : 'bg-rose-100 text-rose-800'
                          }`}
                        >
                          {log.status || 'OK'}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

    </div>
  );
}

function roundGB(mbVal) {
  if (!mbVal) return '0.0';
  return (Number(mbVal) / 1024).toFixed(1);
}
