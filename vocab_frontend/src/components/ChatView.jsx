import React, { useState, useEffect, useRef } from 'react';
import {
  Send,
  Bot,
  User,
  Sparkles,
  RefreshCw,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import VocabCard from './VocabCard';
import SidebarHistory from './SidebarHistory';
import {
  streamChatMessage,
  saveNotebookWord,
  deleteNotebookWord,
  getConversationMessages,
  createConversation,
} from '../services/api';

export default function ChatView({
  selectedLevel,
  onSelectLevel,
  onStatsUpdate,
  initialQuery = '',
  currentUser,
  onLogout,
  setActiveTab,
  onNavigateToAdmin,
}) {
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      isWelcome: true,
      content:
        'Xin chào bạn! Mình là Trợ lý Tra cứu Từ vựng Tiếng Anh A1–B2.\n\nNhập bất kỳ từ vựng tiếng Anh nào để tra cứu nghĩa, cấp độ CEFR, phiên âm IPA, nghe phát âm chuẩn và xem câu ví dụ thực tế nhé!',
      suggestions: [
        'generous nghĩa là gì?',
        'Cho ví dụ với từ improve',
        'Phân biệt borrow và lend',
        'Từ vựng trình độ A1 phổ biến',
      ],
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
      return typeof window !== 'undefined' ? window.innerWidth >= 1024 : true;
    } catch (e) {
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
    } catch (e) {}
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
            } catch (e) {
              meta = {};
            }
          }
          return {
            id: String(m.id || Date.now() + Math.random()),
            role: m.role,
            content: m.content,
            meta: meta,
            cardData: m.cardData || extractCardFromContent(m.content, meta),
            isSaved: false,
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
          'Cuộc trò chuyện mới đã sẵn sàng! Hãy nhập một từ vựng tiếng Anh bạn muốn học hôm nay.',
        suggestions: [
          'confident nghĩa là gì?',
          'Cách dùng từ sustainable',
          'Các từ vựng B2 thường gặp trong IELTS',
        ],
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
                    suggestions: finalPayload.suggestions || [],
                    isStreaming: false,
                  }
                : m
            )
          );
          if (onStatsUpdate) onStatsUpdate();
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

  const handleToggleSave = async (msgId, cardData) => {
    const msg = messages.find((m) => m.id === msgId);
    if (!msg || !cardData?.word) return;

    try {
      if (msg.isSaved) {
        await deleteNotebookWord(cardData.word, userId);
        setMessages((prev) =>
          prev.map((m) => (m.id === msgId ? { ...m, isSaved: false } : m))
        );
      } else {
        await saveNotebookWord(cardData, userId);
        setMessages((prev) =>
          prev.map((m) => (m.id === msgId ? { ...m, isSaved: true } : m))
        );
      }
      if (onStatsUpdate) onStatsUpdate();
    } catch (err) {
      console.error('Toggle save error:', err);
    }
  };

  return (
    <div className="flex h-full w-full max-w-7xl mx-auto overflow-hidden">
      
      {/* ChatGPT-style Sidebar for Conversation History & User Account */}
      <SidebarHistory
        currentUser={currentUser}
        currentConvId={currentConvId}
        onSelectConversation={handleSelectConversation}
        onNewChat={handleNewChat}
        isOpen={sidebarOpen}
        onClose={() => toggleSidebar(false)}
        onLogout={onLogout}
        setActiveTab={setActiveTab}
        onNavigateToAdmin={onNavigateToAdmin}
      />

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col h-full min-h-0 overflow-hidden px-3 sm:px-6 py-3 sm:py-4">
        
        {/* Top Minimal Bar: Sidebar Toggle */}
        <div className="shrink-0 flex items-center justify-between pb-2 mb-1">
          <button
            onClick={() => toggleSidebar()}
            className="px-3 py-1.5 rounded-xl text-slate-600 dark:text-zinc-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-[#262626] bg-white/80 dark:bg-[#171717] border border-slate-200/80 dark:border-white/10 shadow-xs transition-all cursor-pointer flex items-center space-x-2 text-xs font-bold active:scale-98"
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

        {/* Messages Feed: ONLY this container scrolls */}
        <div className="flex-1 min-h-0 overflow-y-auto space-y-4 pr-1 sm:pr-2 overscroll-contain">
          {messages.map((msg) => (
            <div key={msg.id} className="animate-in fade-in duration-150">
              {msg.role === 'user' ? (
                /* User Bubble (ChatGPT Minimalist Style) */
                <div className="flex items-start justify-end space-x-2.5">
                  <div className="max-w-xl bg-gradient-to-r from-emerald-600 to-teal-600 dark:from-[#2f2f2f] dark:to-[#2f2f2f] text-white dark:text-[#ececec] p-3.5 sm:p-4 rounded-3xl rounded-tr-xs shadow-md dark:shadow-none dark:border dark:border-white/10">
                    <p className="text-sm sm:text-base font-semibold dark:font-normal leading-relaxed">
                      {msg.content}
                    </p>
                  </div>
                  <div className="w-8 h-8 rounded-xl bg-slate-900 dark:bg-[#2f2f2f] dark:border dark:border-white/10 text-white dark:text-zinc-200 flex items-center justify-center font-bold text-xs shrink-0 shadow-sm">
                    <User className="w-4 h-4" />
                  </div>
                </div>
              ) : (
                /* Bot Message or VocabCard */
                <div className="flex items-start space-x-2.5">
                  <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-500 to-teal-600 text-white flex items-center justify-center font-black text-base shrink-0 shadow-md shadow-emerald-500/20">
                    📚
                  </div>

                  <div className="flex-1 max-w-3xl space-y-3">
                    {msg.cardData ? (
                      /* Rich Interactive Vocabulary Card */
                      <VocabCard
                        cardData={msg.cardData}
                        meta={msg.meta}
                        isSaved={msg.isSaved}
                        onToggleSave={(data) => handleToggleSave(msg.id, data)}
                        onSelectSuggestion={handleSend}
                      />
                    ) : (
                      /* Regular text message / Streaming text */
                      <div className={`bg-white dark:bg-[#262626] rounded-3xl p-4 sm:p-5 border shadow-xs text-slate-800 dark:text-[#ececec] leading-relaxed text-sm sm:text-base whitespace-pre-line ${
                        msg.isError ? 'border-rose-300 dark:border-rose-800 bg-rose-50/50 dark:bg-rose-950/40 text-rose-900 dark:text-rose-200' : 'border-slate-200 dark:border-white/10'
                      }`}>
                        {msg.content || (
                          <span className="text-slate-400 dark:text-zinc-500 italic">Đang nhận dữ liệu...</span>
                        )}
                        {msg.isStreaming && (
                          <span className="inline-block w-2 h-4 ml-1 bg-emerald-500 animate-pulse align-middle" />
                        )}
                      </div>
                    )}

                    {/* Suggestion Chips */}
                    {msg.suggestions && msg.suggestions.length > 0 && !msg.isStreaming && (
                      <div className="flex flex-wrap gap-2 pt-1">
                        <span className="text-xs font-bold text-slate-400 dark:text-zinc-500 self-center">Gợi ý tiếp theo:</span>
                        {msg.suggestions.map((sug, sIdx) => (
                          <button
                            key={sIdx}
                            onClick={() => handleSend(sug)}
                            className="px-3.5 py-1.5 rounded-full bg-white dark:bg-[#262626] hover:bg-emerald-50 dark:hover:bg-[#303030] hover:border-emerald-300 dark:hover:border-emerald-500/40 text-slate-700 dark:text-zinc-300 hover:text-emerald-800 dark:hover:text-white text-xs font-bold border border-slate-200 dark:border-white/10 shadow-2xs transition-all cursor-pointer flex items-center space-x-1"
                          >
                            <span>{sug}</span>
                            <span className="text-emerald-500 dark:text-emerald-400">↗</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}

          {/* Streaming Status Banner */}
          {streamingStatus && (
            <div className="flex items-center space-x-2.5 text-emerald-700 dark:text-emerald-300 bg-emerald-50/80 dark:bg-[#262626] border border-emerald-200/80 dark:border-emerald-500/30 px-4 py-2.5 rounded-2xl text-xs font-bold animate-pulse max-w-md">
              <Loader2 className="w-4 h-4 animate-spin text-emerald-600 dark:text-emerald-400" />
              <span>{streamingStatus}</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Bottom Chat Input Form: Always stays at bottom without overlapping */}
        <div className="shrink-0 pt-2 sm:pt-3">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="relative flex items-center bg-white dark:bg-[#2f2f2f] rounded-3xl border-2 border-slate-200 dark:border-white/10 shadow-md dark:shadow-2xl dark:shadow-black/40 focus-within:border-emerald-500 dark:focus-within:border-white/30 focus-within:ring-4 focus-within:ring-emerald-500/15 transition-all p-1.5"
          >
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Nhập từ vựng tiếng Anh bất kỳ (ví dụ: 'generous', 'accommodate', 'cách dùng mitigate')..."
              className="w-full py-2.5 sm:py-3 px-3 sm:px-4 text-slate-800 dark:text-[#ececec] placeholder-slate-400 dark:placeholder-zinc-500 font-medium text-sm sm:text-base focus:outline-hidden bg-transparent"
            />

            <button
              type="button"
              onClick={handleNewChat}
              title="Cuộc trò chuyện mới"
              className="p-2 sm:p-2.5 rounded-xl text-slate-400 dark:text-zinc-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/10 transition-colors mr-1 cursor-pointer"
            >
              <RefreshCw className="w-4 h-4" />
            </button>

            <button
              type="submit"
              disabled={!inputValue.trim() || isLoading}
              className="flex items-center justify-center w-8 sm:w-9 h-8 sm:h-9 rounded-full bg-emerald-600 dark:bg-white hover:bg-emerald-700 dark:hover:bg-zinc-200 text-white dark:text-black font-black text-xs sm:text-sm shadow-md shadow-emerald-500/25 dark:shadow-none disabled:opacity-30 disabled:cursor-not-allowed active:scale-95 transition-all cursor-pointer shrink-0"
              title="Gửi câu hỏi"
            >
              <Send className="w-4 h-4 ml-0.5" />
            </button>
          </form>
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
      l.toLowerCase().startsWith('từ bạn tìm kiếm:')
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
    const match = levelLine.match(/(A1|A2|B1|B2)/i);
    if (match) level = match[1].toUpperCase();
  }

  // Extract IPA
  let ipa = '';
  const pronLine = lines.find((l) =>
    l.toLowerCase().includes('phát âm:') || l.includes('/')
  );
  if (pronLine) {
    const match = pronLine.match(/\/([^\/]+)\//);
    if (match) ipa = `/${match[1]}/`;
  }

  // Primary meaning
  const meaningLines = lines.filter(
    (l) =>
      !l.toLowerCase().startsWith('từ bạn tìm kiếm:') &&
      !l.toLowerCase().includes('trình độ:') &&
      !l.toLowerCase().includes('phát âm:') &&
      !l.startsWith('•') &&
      !l.toLowerCase().includes('ví dụ:')
  );
  const primary_meaning = meaningLines[0] || '';

  // Examples
  const exampleLines = lines
    .filter((l) => l.startsWith('•') || l.toLowerCase().startsWith('ví dụ:'))
    .map((l) => l.replace(/^[•\s\-\*]+|(?:Ví dụ|Example):\s*/i, '').trim());

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
