import React, { useState, useEffect, useRef } from 'react';
import {
  Send,
  User,
  RefreshCw,
  PanelLeftClose,
  PanelLeftOpen,
  Loader2,
  Sparkles,
  MessageSquare,
  Plus,
  ArrowRight,
} from 'lucide-react';
import VocabCard from './VocabCard';
import SidebarHistory from './SidebarHistory';
import {
  streamChatMessage,
  getConversationMessages,
  createConversation,
} from '../services/api';

export default function ChatView({
  selectedLevel,
  initialQuery = '',
  currentUser,
  onLogout,
  onNavigateToAdmin,
}) {
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      isWelcome: true,
      content:
        'Xin chào bạn! Mình là Chatbot cho từ vựng tiếng Anh.\n\nNhập bất kỳ từ vựng tiếng Anh nào để bắt đầu tra cứu nghĩa, cấp độ CEFR, phiên âm IPA, nghe phát âm chuẩn và xem câu ví dụ thực tế nhé!',
    },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [streamingStatus, setStreamingStatus] = useState(null);
  const [currentConvId, setCurrentConvId] = useState(null);

  // Lưu và khôi phục trạng thái mở/đóng Sidebar theo từng người dùng
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    try {
      const storageKey = `vocab_sidebar_open_${currentUser?.id || 'default'}`;
      const saved = localStorage.getItem(storageKey);
      if (saved !== null) {
        return saved === 'true';
      }
      return typeof window !== 'undefined' ? window.innerWidth >= 768 : true;
    } catch {
      return true;
    }
  });

  const toggleSidebar = (forceState) => {
    setSidebarOpen((prev) => {
      const nextState = typeof forceState === 'boolean' ? forceState : !prev;
      try {
        const storageKey = `vocab_sidebar_open_${currentUser?.id || 'default'}`;
        localStorage.setItem(storageKey, String(nextState));
      } catch (e) {
        console.error('Failed to save sidebar state:', e);
      }
      return nextState;
    });
  };

  useEffect(() => {
    if (!currentUser?.id) return;
    try {
      const storageKey = `vocab_sidebar_open_${currentUser.id}`;
      const saved = localStorage.getItem(storageKey);
      if (saved !== null) {
        setSidebarOpen(saved === 'true');
      }
    } catch {}
  }, [currentUser?.id]);

  const messagesEndRef = useRef(null);
  const userId = currentUser?.id || 'default_user';

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingStatus, isLoading]);

  // Handle initialQuery if passed from DiscoveryView
  useEffect(() => {
    if (initialQuery && initialQuery.trim()) {
      handleSend(initialQuery.trim());
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuery]);

  // Load past conversation messages when switching conversations
  const handleSelectConversation = async (convOrId) => {
    const targetId = typeof convOrId === 'object' && convOrId !== null ? convOrId.id : convOrId;
    if (!targetId || targetId === currentConvId) return;
    setCurrentConvId(targetId);
    setIsLoading(true);
    setStreamingStatus('Đang tải lịch sử cuộc trò chuyện...');

    try {
      const res = await getConversationMessages(targetId, userId);
      const rawMessages = Array.isArray(res) ? res : (res?.messages || []);
      if (rawMessages && rawMessages.length > 0) {
        const parsed = rawMessages.map((m) => {
          let meta = {};
          if (m.meta) {
            meta = typeof m.meta === 'string' ? JSON.parse(m.meta) : m.meta;
          } else if (m.meta_json) {
            try {
              meta = typeof m.meta_json === 'string' ? JSON.parse(m.meta_json) : m.meta_json;
            } catch {
              meta = {};
            }
          }
          return {
            id: String(m.id || Date.now() + Math.random()),
            role: m.role,
            content: m.content,
            meta: meta,
            cardData: m.cardData || extractCardFromContent(m.content, meta),
          };
        });
        setMessages(parsed);
      } else {
        handleNewChat();
      }
    } catch (err) {
      console.error('Failed to load conversation:', err);
    } finally {
      setIsLoading(false);
      setStreamingStatus(null);
    }
  };

  // Create new chat
  const handleNewChat = () => {
    setCurrentConvId(null);
    setStreamingStatus(null);
    setMessages([
      {
        id: `welcome_${Date.now()}`,
        role: 'assistant',
        isWelcome: true,
        content:
          'Cuộc trò chuyện mới đã sẵn sàng! Hãy nhập một từ vựng tiếng Anh mà bạn muốn học hôm nay.',
      },
    ]);
  };

  // Send message and stream SSE
  const handleSend = async (queryText) => {
    const text = (queryText || inputValue).trim();
    if (!text || isLoading) return;

    setInputValue('');
    const userMsgId = `user_${Date.now()}`;
    const botMsgId = `bot_${Date.now()}`;

    // Add user message to UI
    setMessages((prev) => [
      ...prev,
      {
        id: userMsgId,
        role: 'user',
        content: text,
        level: selectedLevel,
      },
    ]);

    setIsLoading(true);
    setStreamingStatus('Đang kết nối hệ thống...');

    // Prepare assistant placeholder message
    setMessages((prev) => [
      ...prev,
      {
        id: botMsgId,
        role: 'assistant',
        content: '',
        isStreaming: true,
      },
    ]);

    try {
      let activeId = currentConvId;
      if (!activeId) {
        // Create conversation record in backend
        try {
          const newConvRes = await createConversation(userId, text.slice(0, 35));
          const newConv = newConvRes?.conversation || newConvRes;
          if (newConv && newConv.id) {
            activeId = newConv.id;
            setCurrentConvId(newConv.id);
          }
        } catch (e) {
          console.warn('Could not create conversation record:', e);
        }
      }

      await streamChatMessage({
        query: text,
        level: selectedLevel,
        conversationId: activeId,
        userId: userId,
        onStatus: (statusText) => {
          setStreamingStatus(statusText);
        },
        onToken: (chunk) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === botMsgId
                ? { ...m, content: (m.content || '') + chunk }
                : m
            )
          );
        },
        onFinal: (finalPayload) => {
          setStreamingStatus(null);
          if (finalPayload?.conversation_id) {
            setCurrentConvId(finalPayload.conversation_id);
          }
          setMessages((prev) =>
            prev.map((m) =>
              m.id === botMsgId
                ? {
                    ...m,
                    content: finalPayload.reply,
                    cardData: finalPayload.structured_card,
                    meta: finalPayload.meta,
                    isStreaming: false,
                  }
                : m
            )
          );
        },
        onError: (errMsg) => {
          setStreamingStatus(null);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === botMsgId
                ? {
                    ...m,
                    content: `Không thể kết nối đến chatbot (${errMsg}). Vui lòng kiểm tra lại dịch vụ backend.`,
                    isError: true,
                    isStreaming: false,
                  }
                : m
            )
          );
        },
      });
    } catch (err) {
      console.error('Chat error:', err);
      setStreamingStatus(null);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === botMsgId
            ? {
                ...m,
                content: `Lỗi xử lý: ${err.message}`,
                isError: true,
                isStreaming: false,
              }
            : m
        )
      );
    } finally {
      setIsLoading(false);
      setStreamingStatus(null);
    }
  };

  return (
    <div className="flex h-full w-full overflow-hidden">
      
      {/* Modern Sidebar for Conversation History & User Account */}
      <SidebarHistory
        currentUser={currentUser}
        currentConvId={currentConvId}
        onSelectConversation={handleSelectConversation}
        onNewChat={handleNewChat}
        isOpen={sidebarOpen}
        onClose={() => toggleSidebar(false)}
        onLogout={onLogout}
        onNavigateToAdmin={onNavigateToAdmin}
      />

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col h-full min-h-0 overflow-hidden px-3 sm:px-6 py-2.5 sm:py-3.5">
        
        {/* Top Minimal Bar: Sidebar Toggle, Current Session Title & Quick New Chat */}
        <div className="shrink-0 flex items-center justify-between gap-2 pb-2 mb-1">
          <div className="flex items-center space-x-2">
            <button
              onClick={() => toggleSidebar()}
              className="px-3 py-1.5 rounded-xl text-slate-700 dark:text-zinc-200 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-[#262626] bg-white/90 dark:bg-[#1a1a1a] border border-slate-200/90 dark:border-white/10 shadow-2xs transition-all cursor-pointer flex items-center space-x-2 text-xs font-bold active:scale-[0.98]"
              title={sidebarOpen ? 'Đóng lịch sử cuộc trò chuyện' : 'Mở lịch sử cuộc trò chuyện'}
            >
              {sidebarOpen ? (
                <>
                  <PanelLeftClose className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                  <span>Đóng lịch sử</span>
                </>
              ) : (
                <>
                  <PanelLeftOpen className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                  <span>Lịch sử chat</span>
                </>
              )}
            </button>
          </div>

          
        </div>

        {/* Messages Feed: ONLY this container scrolls */}
        <div className="flex-1 min-h-0 overflow-y-auto pr-1 sm:pr-2 overscroll-contain">
          <div className="max-w-4xl mx-auto w-full space-y-4 pb-2">
            {messages.map((msg) => (
              <div key={msg.id} className="animate-in fade-in duration-150">
                {msg.isWelcome ? (
                  /* Welcome Hero Card with Outer Border & Quick Suggestion Chips */
                  <div className="rounded-3xl border-2 border-emerald-500/30 dark:border-white/10 p-5 sm:p-7 bg-gradient-to-br from-white via-emerald-50/20 to-teal-50/30 dark:from-[#202020] dark:via-[#1e1e1e] dark:to-[#171717] shadow-lg dark:shadow-2xl relative overflow-hidden">
                    <div className="absolute -top-12 -right-12 w-44 h-44 bg-emerald-400/10 rounded-full blur-2xl pointer-events-none" />

                    <div className="flex items-center space-x-3 mb-4">
                      <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-emerald-500 to-teal-600 text-white flex items-center justify-center font-black text-2xl shadow-md shadow-emerald-500/25 border border-white/20 shrink-0">
                        📚
                      </div>
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="text-base sm:text-lg font-black text-slate-900 dark:text-white">
                            Trợ lý Từ Vựng Tiếng Anh
                          </span>
                        </div>
                        <p className="text-xs text-slate-500 dark:text-zinc-400 font-medium">
                          Học từ vựng thông minh, tra cứu chuẩn xác, phát âm bản ngữ và lưu trữ lịch sử cá nhân.
                        </p>
                      </div>
                    </div>

                    <div className="p-3.5 sm:p-4 rounded-2xl bg-white/80 dark:bg-[#252525] border border-slate-200/80 dark:border-white/10 shadow-2xs mb-4">
                      <p className="text-xs sm:text-sm text-slate-700 dark:text-zinc-200 font-medium leading-relaxed">
                        Xin chào! Hãy nhập bất kỳ từ vựng tiếng Anh hoặc tiếng Việt vào ô bên dưới để xem nghĩa, phiên âm IPA, nghe phát âm chuẩn Kokoro TTS và các câu ví dụ thực tế. Hoặc bạn có thể click ngay vào một trong các gợi ý dưới đây:
                      </p>
                    </div>

                    {/* Quick Suggestion Chips */}
                    <div>
                      <div className="text-[11px] font-black uppercase tracking-wider text-slate-400 dark:text-zinc-500 mb-2.5 flex items-center space-x-1.5">
                        <Sparkles className="w-3.5 h-3.5 text-emerald-500" />
                        <span>Gợi ý tra cứu nhanh</span>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                        {[
                          { word: 'amazing', meaning: 'Tuyệt vời, kinh ngạc, phi thường', icon: '🌟' },
                          { word: 'discover', meaning: 'Khám phá ra, tìm ra, phát hiện ra', icon: '🚀' },
                          { word: 'brilliant', meaning: 'Sáng dạ, tài giỏi, xuất sắc, rực rỡ', icon: '💡' },
                          { word: 'future', meaning: 'Tương lai, những điều phía trước', icon: '🎯' },
                        ].map((chip) => (
                          <button
                            key={chip.word}
                            type="button"
                            onClick={() => handleSend(chip.word)}
                            className="flex items-center justify-between p-3 rounded-2xl border border-slate-200/90 dark:border-white/10 bg-white hover:bg-emerald-50/60 dark:bg-[#252525] dark:hover:bg-[#2d2d2d] hover:border-emerald-400 dark:hover:border-emerald-500/50 shadow-2xs transition-all cursor-pointer text-left group"
                          >
                            <div className="flex items-center space-x-2.5">
                              <span className="text-base">{chip.icon}</span>
                              <div>
                                <div className="flex items-center space-x-1.5">
                                  <span className="text-xs sm:text-sm font-extrabold text-slate-800 dark:text-zinc-100 group-hover:text-emerald-600 dark:group-hover:text-emerald-400">
                                    {chip.word}
                                  </span>
                                </div>
                                <div className="text-[11px] text-slate-500 dark:text-zinc-400 font-medium truncate max-w-[170px] sm:max-w-[200px]">
                                  {chip.meaning}
                                </div>
                              </div>
                            </div>
                            <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-emerald-600 group-hover:translate-x-0.5 transition-all shrink-0" />
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : msg.role === 'user' ? (
                  /* User Bubble with Outer Border */
                  <div className="flex items-start justify-end space-x-2.5">
                    <div className="max-w-xl bg-gradient-to-r from-emerald-600 to-teal-600 dark:from-[#2c2c2c] dark:to-[#2c2c2c] text-white dark:text-[#ececec] p-3.5 sm:p-4 rounded-3xl rounded-tr-xs shadow-md border border-emerald-500/40 dark:border-white/15">
                      <p className="text-sm sm:text-base font-semibold dark:font-normal leading-relaxed">
                        {msg.content}
                      </p>
                    </div>
                    <div className="w-8 h-8 rounded-xl bg-slate-900 dark:bg-[#282828] border border-slate-700 dark:border-white/15 text-white dark:text-zinc-200 flex items-center justify-center font-bold text-xs shrink-0 shadow-xs">
                      <User className="w-4 h-4" />
                    </div>
                  </div>
                ) : (
                  /* Bot Message or VocabCard with Outer Border */
                  <div className="flex items-start space-x-2.5">
                    <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-500 to-teal-600 border border-emerald-400/40 text-white flex items-center justify-center font-black text-base shrink-0 shadow-md shadow-emerald-500/20">
                      📚
                    </div>

                    <div className="flex-1 max-w-3xl space-y-3">
                      {msg.cardData ? (
                        /* Rich Interactive Vocabulary Card */
                        <VocabCard
                          cardData={msg.cardData}
                          meta={msg.meta}
                        />
                      ) : (
                        /* Regular text message / Streaming text with Outer Border */
                        <div
                          className={`rounded-3xl p-4 sm:p-5 border-2 shadow-xs leading-relaxed text-sm sm:text-base whitespace-pre-line ${
                            msg.isError
                              ? 'border-rose-300 dark:border-rose-800 bg-rose-50/70 dark:bg-rose-950/40 text-rose-900 dark:text-rose-200'
                              : 'border-slate-200 dark:border-white/15 bg-white dark:bg-[#222222] text-slate-800 dark:text-[#ececec]'
                          }`}
                        >
                          {msg.content || (
                            <span className="text-slate-400 dark:text-zinc-500 italic">
                              Đang phân tích và truy xuất từ vựng...
                            </span>
                          )}
                          {msg.isStreaming && (
                            <span className="inline-block w-2 h-4 ml-1 bg-emerald-500 animate-pulse align-middle" />
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}

            {/* Streaming Status Banner with Outer Border */}
            {streamingStatus && (
              <div className="flex items-center space-x-2.5 text-emerald-800 dark:text-emerald-300 bg-emerald-50/90 dark:bg-[#252525] border border-emerald-300/80 dark:border-emerald-500/40 px-4 py-2.5 rounded-2xl text-xs font-bold animate-pulse max-w-md shadow-xs">
                <Loader2 className="w-4 h-4 animate-spin text-emerald-600 dark:text-emerald-400" />
                <span>{streamingStatus}</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Bottom Chat Input Form: Floating Dock Style */}
        <div className="shrink-0 pt-2 sm:pt-3 max-w-4xl mx-auto w-full">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="relative flex items-center bg-white/95 dark:bg-[#252525]/95 backdrop-blur-md rounded-3xl border-2 border-slate-200/90 dark:border-white/15 shadow-lg dark:shadow-2xl dark:shadow-black/50 focus-within:border-emerald-500 dark:focus-within:border-emerald-400 focus-within:ring-4 focus-within:ring-emerald-500/15 transition-all p-1.5"
          >
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Nhập từ vựng tiếng Anh hoặc tiếng Việt (ví dụ: 'family', 'diligent', 'thành công')..."
              className="w-full py-2.5 sm:py-3 px-3.5 sm:px-4 text-slate-800 dark:text-[#ececec] placeholder-slate-400 dark:placeholder-zinc-500 font-medium text-sm sm:text-base focus:outline-hidden bg-transparent"
            />

            {inputValue && (
              <button
                type="button"
                onClick={() => setInputValue('')}
                className="p-1.5 rounded-full hover:bg-slate-100 dark:hover:bg-zinc-700 text-slate-400 hover:text-slate-600 dark:hover:text-zinc-200 transition-colors mr-1 cursor-pointer text-xs"
                title="Xóa nội dung"
              >
                ✕
              </button>
            )}

            <button
              type="button"
              onClick={handleNewChat}
              title="Khởi tạo cuộc trò chuyện mới"
              className="p-2 sm:p-2.5 rounded-xl text-slate-400 dark:text-zinc-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/10 transition-colors mr-1 cursor-pointer"
            >
              <RefreshCw className="w-4 h-4" />
            </button>

            <button
              type="submit"
              disabled={!inputValue.trim() || isLoading}
              className="flex items-center justify-center w-8 sm:w-9 h-8 sm:h-9 rounded-full bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white font-black text-xs sm:text-sm shadow-md shadow-emerald-500/25 disabled:opacity-30 disabled:cursor-not-allowed active:scale-95 transition-all cursor-pointer shrink-0"
              title="Gửi câu hỏi"
            >
              <Send className="w-4 h-4 ml-0.5" />
            </button>
          </form>

          <div className="flex items-center justify-center space-x-3 text-[11px] text-slate-400 dark:text-zinc-500 pt-1.5 font-medium">
            <span>Nhấn <kbd className="px-1.5 py-0.5 rounded bg-slate-200/70 dark:bg-white/10 text-[10px] font-mono">Enter</kbd> để tra cứu</span>
            <span>•</span>
            <span>Phát âm bản ngữ Kokoro TTS</span>
            <span>•</span>
            <span>Xử lý Cục bộ 100%</span>
          </div>
        </div>

      </div>
    </div>
  );
}

/**
 * Helper to recover a structured card object from raw text and metadata
 * when restoring messages from conversation history database
 */
function extractCardFromContent(content, meta) {
  if (!content) return null;
  const low = content.toLowerCase();
  if (
    low.includes('nằm ngoài phạm vi') ||
    low.includes('chưa có dữ liệu') ||
    low.includes('chưa tìm thấy dữ liệu') ||
    meta?.mode === 'NO_MATCH' ||
    meta?.mode === 'SMALL_TALK'
  ) {
    return null;
  }
  const lines = content.split('\n').map((l) => l.trim()).filter(Boolean);

  let word = meta?.word || '';
  if (!word) {
    const searchLine = lines.find((l) =>
      l.toLowerCase().startsWith('từ bạn tìm kiếm:') ||
      l.toLowerCase().startsWith('từ tiếng anh phù hợp:')
    );
    if (searchLine) {
      word = searchLine.split(':')[1]?.trim() || '';
    }
  }

  // If we don't have a recognizable word, treat as normal message
  if (!word) return null;

  // Extract level
  let level = meta?.level || 'A1';
  const levelLine = lines.find((l) =>
    l.toLowerCase().includes('trình độ:') || l.toLowerCase().includes('level:')
  );
  if (levelLine) {
    const match = levelLine.match(/(A1|A2|B1|B2|C1|C2)/i);
    if (match) level = match[1].toUpperCase();
  }

  // Extract IPA
  let ipa = '';
  const pronLine = lines.find((l) =>
    l.toLowerCase().includes('phát âm:') || l.includes('/')
  );
  if (pronLine) {
    const match = pronLine.match(/\/([^/]+)\//);
    if (match) ipa = `/${match[1]}/`;
  }

  // Primary meaning
  const meaningLines = lines.filter(
    (l) =>
      !l.toLowerCase().startsWith('từ bạn tìm kiếm:') &&
      !l.toLowerCase().startsWith('từ tiếng anh phù hợp:') &&
      !l.toLowerCase().includes('trình độ:') &&
      !l.toLowerCase().includes('phát âm:') &&
      !l.startsWith('•') &&
      !l.toLowerCase().includes('ví dụ:')
  );
  const primary_meaning = meaningLines[0] || '';

  // Examples
  const exampleLines = lines
    .filter((l) => l.startsWith('•') || l.toLowerCase().startsWith('ví dụ:'))
    .map((l) => l.replace(/^[•\s\-*]+|(?:Ví dụ|Example):\s*/i, '').trim());

  return {
    word: word,
    level: level,
    ipa: ipa,
    primary_meaning: primary_meaning,
    primary_example: exampleLines[0] || '',
    blocks: [
      {
        pos: meta?.pos || '',
        meanings: [
          {
            definition: primary_meaning,
            examples: exampleLines,
          },
        ],
      },
    ],
    meta: meta || {},
  };
}
