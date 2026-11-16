import { useEffect, useRef } from 'react';
import Icon from './Icon';

// Navigation and downloads stay separate from the chat request code.
export default function Sidebar({ isOpen, isMobile, toggleSidebar, chats, currentChatId,
  createNewChat, selectChat, disabled, resumeUrl }) {
  const closeButton = useRef(null);

  // Move keyboard focus into the menu when it opens on a phone.
  useEffect(() => {
    if (isOpen && isMobile) closeButton.current?.focus();
  }, [isOpen, isMobile]);

  return (
    <aside id="sidebar" className={`sidebar ${isOpen ? 'open' : ''}`} aria-label="Chat navigation">
      <div className="sidebar-brand">
        <span className="brand-mark" aria-hidden="true">K<span>.</span></span>
        <div><strong>Keertan</strong><span className="brand-caption">AI PORTFOLIO</span></div>
        <button ref={closeButton} className="icon-button close-sidebar-btn" onClick={toggleSidebar} aria-label="Close menu">
          <Icon name="close" />
        </button>
      </div>

      <button className="new-chat-btn" onClick={createNewChat} disabled={disabled}>
        <Icon name="plus" size={18} /> New conversation
      </button>

      <nav className="chat-history" aria-label="Conversations">
        <p className="history-label">YOUR CONVERSATIONS</p>
        {chats.map(chat => (
          <button key={chat.id} className={`history-btn ${chat.id === currentChatId ? 'active' : ''}`}
            onClick={() => selectChat(chat.id)} disabled={disabled}
            aria-current={chat.id === currentChatId ? 'page' : undefined} title={chat.title}>
            <Icon name="chat" size={17} />
            <span className="history-title">{chat.title}</span>
          </button>
        ))}
        <p className="history-note">Chats clear when you refresh.</p>
      </nav>

      <div className="sidebar-footer">
        <p className="resume-label">THE FULL PICTURE</p>
        <a href={resumeUrl} className="resume-btn">
          <Icon name="file" />
          <span><strong>Download resume</strong><small>Experience, skills & projects</small></span>
          <Icon name="arrow" size={17} />
        </a>
        <p className="sidebar-note">A resume. A conversation.<br />A better introduction.</p>
      </div>
    </aside>
  );
}
