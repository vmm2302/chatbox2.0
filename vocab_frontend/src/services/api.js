/**
 * API client service for communicating with the backend FastAPI server.
 * Includes Auth, Conversations, Streaming SSE, Notebook, Discovery, and Admin endpoints.
 */

const API_BASE = '/api';

// -------------------------------------------------------------
// Authentication & User Profile
// -------------------------------------------------------------
export async function getAuthSystemStatus() {
  const res = await fetch(`${API_BASE}/auth/status`);
  if (!res.ok) throw new Error('Failed to get auth status');
  return res.json();
}

export async function loginUser(username, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Đăng nhập không thành công.');
  }
  return data;
}

export async function registerUser(username, password, confirmPassword, displayName) {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username,
      password,
      confirm_password: confirmPassword,
      display_name: displayName,
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Đăng ký không thành công.');
  }
  return data;
}

export async function verifySession(userId) {
  const res = await fetch(`${API_BASE}/auth/me?user_id=${userId}`);
  if (!res.ok) return null;
  return res.json();
}

export async function changePassword(userId, currentPassword, newPassword, confirmPassword) {
  const res = await fetch(`${API_BASE}/auth/change-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId,
      current_password: currentPassword,
      new_password: newPassword,
      confirm_password: confirmPassword,
    }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Không thể đổi mật khẩu.');
  return data;
}

// -------------------------------------------------------------
// Conversations & Chat History
// -------------------------------------------------------------
export async function getConversations(userId, search = '') {
  const params = new URLSearchParams({ user_id: String(userId) });
  if (search) params.set('search', search);
  const res = await fetch(`${API_BASE}/conversations?${params.toString()}`);
  if (!res.ok) return { pinned: [], grouped: { 'Hôm nay': [], '7 ngày gần đây': [], 'Trước đó': [] }, total: 0 };
  return res.json();
}

export async function createConversation(userId, title = 'Cuộc trò chuyện mới') {
  const res = await fetch(`${API_BASE}/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, title }),
  });
  if (!res.ok) throw new Error('Không thể tạo đoạn chat mới.');
  return res.json();
}

export async function getConversationMessages(convId, userId) {
  const res = await fetch(`${API_BASE}/conversations/${convId}/messages?user_id=${userId}`);
  if (!res.ok) throw new Error('Không thể tải tin nhắn.');
  return res.json();
}

export async function renameConversation(convId, userId, title) {
  const res = await fetch(`${API_BASE}/conversations/${convId}/title`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, title }),
  });
  if (!res.ok) throw new Error('Không thể đổi tên.');
  return res.json();
}

export async function togglePinConversation(convId, userId) {
  const res = await fetch(`${API_BASE}/conversations/${convId}/pin?user_id=${userId}`, {
    method: 'PATCH',
  });
  if (!res.ok) throw new Error('Không thể ghim cuộc trò chuyện.');
  return res.json();
}

export async function deleteConversation(convId, userId) {
  const res = await fetch(`${API_BASE}/conversations/${convId}?user_id=${userId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Không thể xóa cuộc trò chuyện.');
  return res.json();
}

export async function clearAllConversations(userId) {
  const res = await fetch(`${API_BASE}/conversations?user_id=${userId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Không thể xóa toàn bộ lịch sử.');
  return res.json();
}

// -------------------------------------------------------------
// Real-time Chat & Streaming (SSE)
// -------------------------------------------------------------
export async function streamChatMessage({
  query,
  level = 'Tất cả',
  conversationId = null,
  userId,
  onStatus,
  onToken,
  onFinal,
  onError,
}) {
  try {
    const res = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        level,
        conversation_id: conversationId,
        user_id: userId,
      }),
    });

    if (!res.ok) {
      throw new Error(`Streaming failed with status: ${res.statusText}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // keep partial line

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith('data: ')) continue;
        const jsonStr = trimmed.replace('data: ', '').trim();
        if (jsonStr === '[DONE]') break;

        try {
          const payload = JSON.parse(jsonStr);
          if (payload.type === 'status' && onStatus) {
            onStatus(payload.text);
          } else if (payload.type === 'token' && onToken) {
            onToken(payload.token);
          } else if (payload.type === 'final' && onFinal) {
            onFinal(payload);
          }
        } catch (e) {
          console.debug('SSE parse skip:', e);
        }
      }
    }
  } catch (err) {
    console.error('SSE Error:', err);
    if (onError) onError(err);
  }
}

// Fallback regular chat endpoint
export async function sendChatMessage(query, level = 'Tất cả', conversationId = null, userId = 1) {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      level,
      conversation_id: conversationId,
      user_id: String(userId),
    }),
  });
  if (!res.ok) throw new Error(`API error: ${res.statusText}`);
  return res.json();
}

export async function searchWords(q, level = null, limit = 10) {
  const params = new URLSearchParams({ q, limit: String(limit) });
  if (level && level !== 'Tất cả') params.set('level', level);
  const res = await fetch(`${API_BASE}/words/search?${params.toString()}`);
  if (!res.ok) return { results: [] };
  return res.json();
}

export async function getDiscoveryWords(level = 'A1', count = 8) {
  const res = await fetch(`${API_BASE}/words/discover?level=${level}&count=${count}`);
  if (!res.ok) return { words: [] };
  return res.json();
}

// -------------------------------------------------------------
// Sổ tay từ vựng & Flashcards
// -------------------------------------------------------------
export async function getNotebookWords(level = null, status = null, userId = 'default_user') {
  const params = new URLSearchParams({ user_id: String(userId) });
  if (level && level !== 'Tất cả') params.set('level', level);
  if (status && status !== 'all') params.set('status', status);
  const res = await fetch(`${API_BASE}/notebook?${params.toString()}`);
  if (!res.ok) return { saved_words: [] };
  return res.json();
}

export async function saveNotebookWord(wordData, userId = 'default_user') {
  const res = await fetch(`${API_BASE}/notebook`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      word: wordData.word,
      level: wordData.level || 'A1',
      ipa: wordData.ipa || '',
      part_of_speech: wordData.primary_pos || wordData.part_of_speech || '',
      meaning: wordData.primary_meaning || wordData.meaning || '',
      example: wordData.primary_example || wordData.example || '',
      collocations: wordData.collocations || '',
      user_id: String(userId),
    }),
  });
  if (!res.ok) throw new Error('Failed to save word');
  return res.json();
}

export async function deleteNotebookWord(word, userId = 'default_user') {
  const res = await fetch(`${API_BASE}/notebook/${encodeURIComponent(word)}?user_id=${userId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete word');
  return res.json();
}

export async function updateNotebookStatus(word, status, incrementReview = true, userId = 'default_user') {
  const res = await fetch(`${API_BASE}/notebook/${encodeURIComponent(word)}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      status,
      user_id: String(userId),
      increment_review: incrementReview,
    }),
  });
  if (!res.ok) throw new Error('Failed to update status');
  return res.json();
}

export async function getStats(userId = 'default_user') {
  const res = await fetch(`${API_BASE}/stats?user_id=${userId}`);
  if (!res.ok) return { total_saved: 0, mastered: 0, learning: 0, by_level: {} };
  return res.json();
}

// -------------------------------------------------------------
// Admin Portal & Knowledge Base Management
// -------------------------------------------------------------
export async function getAdminMetrics(userId) {
  const res = await fetch(`${API_BASE}/admin/metrics?user_id=${userId}`);
  if (!res.ok) throw new Error('Failed to get storage metrics');
  return res.json();
}

export async function getAdminSources(userId) {
  const res = await fetch(`${API_BASE}/admin/sources?user_id=${userId}`);
  if (!res.ok) throw new Error('Failed to get active sources');
  const data = await res.json();
  return Array.isArray(data) ? data : (data.sources || []);
}

export async function uploadAdminFiles(userId, mode, files) {
  const formData = new FormData();
  formData.append('user_id', String(userId));
  formData.append('mode', mode);
  for (const file of files) {
    formData.append('files', file);
  }

  const res = await fetch(`${API_BASE}/admin/upload`, {
    method: 'POST',
    body: formData,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Upload failed');
  return data;
}

export async function clearAdminKnowledgeBase(userId) {
  const res = await fetch(`${API_BASE}/admin/clear-kb?user_id=${userId}`, {
    method: 'POST',
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Clear KB failed');
  return data;
}

export async function getAdminTelemetry(userId) {
  const res = await fetch(`${API_BASE}/admin/telemetry?user_id=${userId}`);
  if (!res.ok) throw new Error('Failed to get telemetry');
  return res.json();
}

export async function getAdminOllama(userId) {
  const res = await fetch(`${API_BASE}/admin/ollama?user_id=${userId}`);
  if (!res.ok) throw new Error('Failed to get Ollama status');
  return res.json();
}

export async function getAdminAuditLogs(userId, limit = 50) {
  const res = await fetch(`${API_BASE}/admin/audit-logs?user_id=${userId}&limit=${limit}`);
  if (!res.ok) throw new Error('Failed to get audit logs');
  const data = await res.json();
  return Array.isArray(data) ? data : (data.logs || []);
}

// -------------------------------------------------------------
// Admin: User & Account Management (Migrated from app.py & admin_dashboard.py)
// -------------------------------------------------------------
export async function getAdminUserStats(userId) {
  const res = await fetch(`${API_BASE}/admin/users/stats?user_id=${userId}`);
  if (!res.ok) throw new Error('Failed to get user stats');
  return res.json();
}

export async function getAdminUsers(userId, { search = '', role = '', isActive = null, limit = 100, offset = 0 } = {}) {
  const params = new URLSearchParams({ user_id: String(userId), limit: String(limit), offset: String(offset) });
  if (search) params.append('search', search);
  if (role && role !== 'all') params.append('role', role);
  if (isActive !== null && isActive !== undefined && isActive !== 'all') {
    params.append('is_active', String(isActive));
  }
  const res = await fetch(`${API_BASE}/admin/users?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to get user list');
  const data = await res.json();
  return data.users || [];
}

export async function updateAdminUserStatus(userId, targetId, isActive) {
  const res = await fetch(`${API_BASE}/admin/users/${targetId}/status?user_id=${userId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ is_active: Boolean(isActive) }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Cập nhật trạng thái người dùng thất bại');
  return data;
}

export async function updateAdminUserRole(userId, targetId, role) {
  const res = await fetch(`${API_BASE}/admin/users/${targetId}/role?user_id=${userId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ role }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Cập nhật vai trò thất bại');
  return data;
}

export async function resetAdminUserPassword(userId, targetId, newPassword) {
  const res = await fetch(`${API_BASE}/admin/users/${targetId}/reset-password?user_id=${userId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ new_password: newPassword }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Đặt lại mật khẩu thất bại');
  return data;
}

export async function deleteAdminUser(userId, targetId) {
  const res = await fetch(`${API_BASE}/admin/users/${targetId}?user_id=${userId}`, {
    method: 'DELETE',
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Xóa người dùng thất bại');
  return data;
}
