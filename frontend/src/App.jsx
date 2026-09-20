import { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatArea from './components/ChatArea';
import './index.css';

// Vercel deployment: Set VITE_API_URL in your Vercel project environment variables
const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/chat';

function App() {
  const [theme, setTheme] = useState('dark');
  const [isSidebarOpen, setIsSidebarOpen] = useState(window.innerWidth > 768);

  // Chats structure: { id: string, title: string, messages: [] }
  const [chats, setChats] = useState([
    { id: Date.now().toString(), title: "New Chat", messages: [] }
  ]);
  const [currentChatId, setCurrentChatId] = useState(chats[0].id);
  const [isTyping, setIsTyping] = useState(false);

  const currentChat = chats.find(c => c.id === currentChatId) || chats[0];

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  // Handle window resize for sidebar
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth <= 768) {
        setIsSidebarOpen(false);
      } else {
        setIsSidebarOpen(true);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const toggleTheme = () => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  };

  const toggleSidebar = () => {
    setIsSidebarOpen(!isSidebarOpen);
  };

  const createNewChat = () => {
    const newChat = { id: Date.now().toString(), title: "New Chat", messages: [] };
    setChats(prev => [newChat, ...prev]);
    setCurrentChatId(newChat.id);
    if (window.innerWidth <= 768) setIsSidebarOpen(false);
  };

  const selectChat = (id) => {
    setCurrentChatId(id);
    if (window.innerWidth <= 768) setIsSidebarOpen(false);
  };

  const handleSend = async (question) => {
    if (!question.trim()) return;

    // Add user message
    let updatedChats = chats.map(chat => {
      if (chat.id === currentChatId) {
        const isFirstMessage = chat.messages.length === 0;
        return {
          ...chat,
          title: isFirstMessage ? question.substring(0, 30) + '...' : chat.title,
          messages: [...chat.messages, { text: question, sender: 'user' }]
        };
      }
      return chat;
    });
    setChats(updatedChats);
    setIsTyping(true);

    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      setChats(prevChats => prevChats.map(chat => {
        if (chat.id === currentChatId) {
          return {
            ...chat,
            messages: [...chat.messages, { text: data.answer, sender: 'ai' }]
          };
        }
        return chat;
      }));
    } catch (error) {
      console.error('Error fetching chat response:', error);
      setChats(prevChats => prevChats.map(chat => {
        if (chat.id === currentChatId) {
          return {
            ...chat,
            messages: [...chat.messages, { text: 'Sorry, I encountered an error connecting to the server.', sender: 'ai' }]
          };
        }
        return chat;
      }));
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="app-container">
      <Sidebar
        isOpen={isSidebarOpen}
        toggleSidebar={toggleSidebar}
        chats={chats}
        currentChatId={currentChatId}
        createNewChat={createNewChat}
        selectChat={selectChat}
        disabled={isTyping}
      />

      {/* Overlay for mobile sidebar */}
      {isSidebarOpen && window.innerWidth <= 768 && (
        <div className="sidebar-overlay" onClick={toggleSidebar}></div>
      )}

      <ChatArea
        theme={theme}
        toggleTheme={toggleTheme}
        toggleSidebar={toggleSidebar}
        isSidebarOpen={isSidebarOpen}
        messages={currentChat.messages}
        isTyping={isTyping}
        onSend={handleSend}
      />
    </div>
  );
}

export default App;
