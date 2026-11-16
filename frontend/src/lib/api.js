// Local development uses your Python server. Public visitors use Render.
export function getApiUrl(isDevelopment, configuredUrl) {
  if (isDevelopment) return 'http://127.0.0.1:8000/chat';
  const url = new URL(configuredUrl?.trim() || 'https://hiremeai-ai-portfolio.onrender.com');
  // Questions must go to /chat, even if Vercel's setting contains only the server URL.
  url.pathname = '/chat';
  return url.href;
}
