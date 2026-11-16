import { useState, useRef, useEffect } from 'react';
import Icon from './Icon';

// These are questions, not claims about what is in the resume.
const suggestions = [
  { label: 'Experience & skills', text: 'What can Keertan bring to a team?', question: "What are Keertan's experience and top skills?" },
  { label: 'Projects', text: 'Explore the work behind the resume.', question: 'Tell me about the projects Keertan has worked on.' },
  { label: 'Education', text: 'Get to know the background.', question: "Tell me about Keertan's education." },
  { label: 'The bigger picture', text: 'See what makes a good fit.', question: 'Why should we hire Keertan?' },
];

// Show messages and input here. App.jsx owns chats and network requests.
export default function ChatArea({ theme, toggleTheme, toggleSidebar, isSidebarOpen, isMobile,
  messages, chatId, isTyping, onSend, onStop }) {
  const [input, setInput] = useState('');
  const chatBox = useRef(null);
  const inputBox = useRef(null);
  const followAnswer = useRef(true);
  const menuButton = useRef(null);

  // A new chat starts at the bottom. Do not pull readers down if they scroll up.
  useEffect(() => {
    followAnswer.current = true;
  }, [chatId]);

  useEffect(() => {
    if (isTyping) followAnswer.current = true;
  }, [isTyping]);

  useEffect(() => {
    if (followAnswer.current && chatBox.current) {
      chatBox.current.scrollTop = chatBox.current.scrollHeight;
    }
  }, [messages, chatId]);

  useEffect(() => {
    if (!isTyping && !isMobile) inputBox.current?.focus();
  }, [isTyping, chatId, isMobile]);

  // Closing the phone menu returns focus to its button.
  useEffect(() => {
    if (!isSidebarOpen && isMobile) menuButton.current?.focus();
  }, [isSidebarOpen, isMobile]);

  const handleSubmit = (event) => {
    event.preventDefault();
    if (!input.trim() || isTyping) return;
    onSend(input);
    setInput('');
  };

  const handleScroll = () => {
    const box = chatBox.current;
    followAnswer.current = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
  };

  return (
    <main className="chat-area" inert={isMobile && isSidebarOpen}>
      <header className="chat-header">
        <div className="header-left">
          <button ref={menuButton} className="icon-button" onClick={toggleSidebar}
            aria-label={isSidebarOpen ? 'Hide menu' : 'Open menu'}
            aria-expanded={isSidebarOpen} aria-controls="sidebar">
            <Icon name="menu" />
          </button>
          <div><span className="header-title">Keertan's AI</span><span className="header-subtitle">A personal introduction</span></div>
        </div>
        <div className="header-right">
          <span className="resume-badge"><span /> Resume-based answers</span>
          <button className="icon-button theme-toggle" onClick={toggleTheme}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>
            <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
          </button>
        </div>
      </header>

      <div className="chat-box" ref={chatBox} onScroll={handleScroll}>
        {messages.length === 0 ? (
          <section className="empty-state" aria-labelledby="welcome-title">
            <span className="welcome-mark" aria-hidden="true">K<span>.</span></span>
            <p className="eyebrow">THE PERSON BEHIND THE RESUME</p>
            <h1 id="welcome-title">Get to know <span>Keertan.</span></h1>
            <p className="welcome-text">Explore my experience, projects, and skills.<br className="desktop-break" /> Pick a starting point, or ask what's on your mind.</p>
            <div className="suggestions-grid">
              {suggestions.map(item => (
                <button key={item.label} className="suggestion-card" onClick={() => onSend(item.question)} disabled={isTyping}>
                  <span><strong>{item.label}</strong><span>{item.text}</span></span>
                  <Icon name="arrow" size={18} />
                </button>
              ))}
            </div>
            <p className="welcome-note"><span /> Answers come from my resume.</p>
          </section>
        ) : (
          <div className="messages-container" role="log" aria-label="Conversation" aria-live="polite" aria-busy={isTyping}>
            {messages.map((message, index) => (
              <article key={message.id || index} className={`message-wrapper ${message.sender}-message`}>
                {message.sender === 'ai' && <span className="message-avatar" aria-hidden="true">K.</span>}
                <div className="message-body">
                  <p className="message-label">{message.sender === 'ai' ? "Keertan's AI" : 'You'}</p>
                  <div className={`message-content ${message.failed ? 'message-error' : ''}`}>
                    {isTyping && message.sender === 'ai' && !message.text
                      ? <span className="typing-indicator" aria-label="Preparing answer"><span /><span /><span /></span>
                      : message.text}
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>

      <div className="chat-input-area">
        <form className="chat-form" onSubmit={handleSubmit}>
          <label className="sr-only" htmlFor="chat-input">Ask about Keertan</label>
          <textarea id="chat-input" ref={inputBox} className="chat-input" rows={2}
            placeholder="What would you like to know?" value={input}
            onChange={event => setInput(event.target.value)} disabled={isTyping} maxLength={500}
            onKeyDown={event => {
              // Enter sends; Shift+Enter adds a line. Leave IME text entry alone.
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) handleSubmit(event);
            }} />
          <div className="composer-bottom">
            <span className="input-hint">{isTyping ? 'Writing an answer...' : 'Enter to send ? Shift + Enter for a new line'}</span>
            <span className="character-count">{input.length}/500</span>
            <button type={isTyping ? 'button' : 'submit'} className={`send-btn ${isTyping ? 'stop-btn' : ''}`}
              onClick={isTyping ? onStop : undefined} disabled={!isTyping && !input.trim()}
              aria-label={isTyping ? 'Stop generating' : 'Send message'} title={isTyping ? 'Stop generating' : 'Send message'}>
              <Icon name={isTyping ? 'stop' : 'send'} size={20} />
            </button>
          </div>
        </form>
        <p className="disclaimer">AI can make mistakes. Check important details in my resume.</p>
      </div>
    </main>
  );
}
