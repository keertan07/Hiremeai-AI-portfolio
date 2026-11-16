import { useState, useEffect, useRef } from 'react';
import { readChatStream } from './lib/chatStream';
import Sidebar from './components/Sidebar';
import ChatArea from './components/ChatArea';
import './index.css';

// Set VITE_API_URL for deployment. Both chat and downloads use this backend.
const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/chat';
const RESUME_URL = new URL('resume', new URL(API_URL, window.location.origin)).href;

function App() {
  const [theme, setTheme] = useState('dark');
  const [isMobile, setIsMobile] = useState(() => window.matchMedia('(max-width: 768px)').matches);
  const [isSidebarOpen, setIsSidebarOpen] = useState(!isMobile);

  // Each chat holds its own ID, title, and displayed messages. Refresh clears them.
  const [chats, setChats] = useState(() => [
    { id: crypto.randomUUID(), title: 'New conversation', messages: [] }
  ]);
  const [currentChatId, setCurrentChatId] = useState(chats[0].id);
  const [isTyping, setIsTyping] = useState(false);
  const activeRequest = useRef(null);

  // Cancel the browser connection if this component is removed.
  useEffect(() => () => activeRequest.current?.abort(), []);

  const currentChat = chats.find(c => c.id === currentChatId) || chats[0];

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  // Only change menu layout when crossing the phone/desktop breakpoint.
  useEffect(() => {
    const screen = window.matchMedia('(max-width: 768px)');
    const handleResize = (event) => {
      setIsMobile(event.matches);
      setIsSidebarOpen(!event.matches);
    };
    screen.addEventListener('change', handleResize);
    return () => screen.removeEventListener('change', handleResize);
  }, []);

  // Escape closes the menu for keyboard users.
  useEffect(() => {
    const closeMenu = (event) => {
      if (event.key === 'Escape') setIsSidebarOpen(false);
    };
    window.addEventListener('keydown', closeMenu);
    return () => window.removeEventListener('keydown', closeMenu);
  }, []);

  const toggleTheme = () => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  };

  const toggleSidebar = () => {
    setIsSidebarOpen(open => !open);
  };

  const createNewChat = () => {
    const newChat = {
      id: crypto.randomUUID(),
      title: 'New conversation',
      messages: []
    };
    setChats(prev => [newChat, ...prev]);
    setCurrentChatId(newChat.id);
    if (isMobile) setIsSidebarOpen(false);
  };

  const selectChat = (id) => {
    setCurrentChatId(id);
    if (isMobile) setIsSidebarOpen(false);
  };

  const handleSend = async (question) => {
    question = question.trim();
    if (!question || question.length > 500 || activeRequest.current) return;

    // Capture IDs now so incoming chunks always update the originating chat/message.
    const chatId = currentChatId;
    const answerId = crypto.randomUUID();
    const controller = new AbortController();
    activeRequest.current = controller;
    setIsTyping(true);
    setChats(prev => prev.map(chat => chat.id === chatId ? {
      ...chat,
      title: chat.messages.length === 0 ? question.substring(0, 30) + '...' : chat.title,
      messages: [...chat.messages,
        { text: question, sender: 'user' },
        { id: answerId, text: '', sender: 'ai' }]
    } : chat));

    // Replace the same placeholder as tokens arrive, rather than adding new bubbles.
    const updateAnswer = (text, failed = false) => setChats(prev => prev.map(chat => chat.id === chatId ? {
      ...chat,
      messages: chat.messages.map(message => message.id === answerId ? { ...message, text, failed } : message)
    } : chat));

    let answer = '';
    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
        body: JSON.stringify({ conversation_id: chatId, question, stream: true }),
        signal: controller.signal
      });
      if (!response.ok) {
        const error = await response.json().catch(() => null);
        const detail = typeof error?.detail === 'string' ? error.detail : null;
        throw new Error(detail || (response.status === 429
          ? 'Too many messages. Please wait a minute and try again.'
          : `Unable to send message (${response.status}). Please try again.`));
      }

      await readChatStream(response, event => {
        if (event.type === 'delta') {
          answer += event.text;
          updateAnswer(answer);
        } else if (event.type === 'done') {
          updateAnswer(event.answer); // Use the backend's validated, final answer.
        }
      });
    } catch (error) {
      // A partial answer is not a completed history turn; mark stopped output clearly.
      if (controller.signal.aborted) {
        updateAnswer(answer ? `${answer}\n\n[Stopped]` : 'Response stopped.', true);
      } else {
        console.error('Chat stream failed:', error);
        updateAnswer(error instanceof TypeError ? "Can't reach the server. Please try again."
          : error.message || 'Unable to finish the answer. Please try again.', true);
      }
    } finally {
      activeRequest.current = null;
      setIsTyping(false);
    }
  };

  return (
    <div className="app-container">
      <Sidebar
        isOpen={isSidebarOpen}
        isMobile={isMobile}
        resumeUrl={RESUME_URL}
        toggleSidebar={toggleSidebar}
        chats={chats}
        currentChatId={currentChatId}
        createNewChat={createNewChat}
        selectChat={selectChat}
        disabled={isTyping}
      />

      {/* Overlay for mobile sidebar */}
      {isSidebarOpen && isMobile && (
        <button className="sidebar-overlay" onClick={toggleSidebar} aria-label="Close menu" />
      )}

      <ChatArea
        key={currentChatId}
        chatId={currentChatId}
        theme={theme}
        toggleTheme={toggleTheme}
        toggleSidebar={toggleSidebar}
        isSidebarOpen={isSidebarOpen}
        isMobile={isMobile}
        messages={currentChat.messages}
        isTyping={isTyping}
        onSend={handleSend}
        onStop={() => activeRequest.current?.abort()}
      />
    </div>
  );
}

export default App;
