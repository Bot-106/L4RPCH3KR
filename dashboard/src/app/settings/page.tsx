"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { setApiKey, getApiKey, clearApiKey, getAllApiKeys, LLMProvider } from "@/lib/api-keys";

export default function SettingsPage() {
  const [anthropicKey, setAnthropicKey] = useState("");
  const [openaiKey, setOpenaiKey] = useState("");
  const [anthropicSaved, setAnthropicSaved] = useState(false);
  const [openaiSaved, setOpenaiSaved] = useState(false);
  const [loading, setLoading] = useState(true);

  // Load existing keys on mount
  useEffect(() => {
    const existing = getAllApiKeys();
    if (existing.anthropic) setAnthropicKey(existing.anthropic);
    if (existing.openai) setOpenaiKey(existing.openai);
    setLoading(false);
  }, []);

  const handleSaveAnthropicKey = () => {
    if (anthropicKey.trim()) {
      setApiKey("anthropic", anthropicKey);
      setAnthropicSaved(true);
      setTimeout(() => setAnthropicSaved(false), 3000);
    }
  };

  const handleSaveOpenaiKey = () => {
    if (openaiKey.trim()) {
      setApiKey("openai", openaiKey);
      setOpenaiSaved(true);
      setTimeout(() => setOpenaiSaved(false), 3000);
    }
  };

  const handleClearAnthropicKey = () => {
    clearApiKey("anthropic");
    setAnthropicKey("");
  };

  const handleClearOpenaiKey = () => {
    clearApiKey("openai");
    setOpenaiKey("");
  };

  if (loading) return <div className="p-8">Loading...</div>;

  return (
    <main className="arcade-page">
      <header className="arcade-masthead">
        <div className="flex items-center gap-5">
          <Link href="/events" className="flex items-center gap-5">
            <div className="arcade-mark" aria-hidden="true">
              <i /><i /><i className="w" /><i className="w" /><i className="w" /><i className="w" /><i /><i />
              <i /><i className="w" /><i className="g" /><i className="g" /><i className="g" /><i className="g" /><i className="w" /><i />
              <i className="w" /><i className="g" /><i className="g" /><i className="w" /><i className="w" /><i className="g" /><i className="g" /><i className="w" />
              <i className="w" /><i className="g" /><i className="w" /><i className="g" /><i className="g" /><i className="g" /><i className="g" /><i className="w" />
              <i className="w" /><i className="g" /><i className="g" /><i className="g" /><i className="g" /><i className="g" /><i className="g" /><i className="w" />
              <i className="w" /><i className="g" /><i className="g" /><i className="g" /><i className="g" /><i className="g" /><i className="g" /><i className="w" />
              <i /><i className="w" /><i className="g" /><i className="g" /><i className="g" /><i className="g" /><i className="w" /><i />
              <i /><i /><i className="w" /><i className="w" /><i className="w" /><i className="w" /><i /><i />
            </div>
            <div className="arcade-wordmark">LarpChecker</div>
          </Link>
        </div>
        <nav className="flex flex-wrap gap-3 text-[10px]">
          <a className="px-3 py-2 text-white" href="/events">EVENTS</a>
          <a className="px-3 py-2 text-white" href="/leaderboard">LARPERBOARD</a>
          <span className="bg-white px-3 py-2 text-black">SETTINGS</span>
        </nav>
      </header>
      <div className="pixel-strip" />
      <div className="mx-auto max-w-2xl p-8">
        <h1 className="text-3xl font-bold mb-8">API KEY SETTINGS</h1>
        
        <p className="text-gray-600 mb-6">
          Configure your own API keys to use with the LLM features. Keys are stored securely in your browser cookies and never sent to our servers.
        </p>

        <div className="space-y-8">
        {/* Anthropic API Key Section */}
        <div className="border rounded-lg p-6 bg-white shadow-sm">
          <h2 className="text-xl font-semibold mb-4">Anthropic API Key</h2>
          <p className="text-gray-600 text-sm mb-4">
            Get your API key from <a href="https://console.anthropic.com" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">console.anthropic.com</a>
          </p>
          
          <div className="space-y-3">
            <input
              type="password"
              value={anthropicKey}
              onChange={(e) => setAnthropicKey(e.target.value)}
              placeholder="sk-ant-..."
              className="w-full px-4 py-2 border rounded-lg font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            
            <div className="flex gap-3">
              <button
                onClick={handleSaveAnthropicKey}
                disabled={!anthropicKey.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 font-medium"
              >
                Save Key
              </button>
              {anthropicKey && (
                <button
                  onClick={handleClearAnthropicKey}
                  className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 font-medium"
                >
                  Clear
                </button>
              )}
            </div>

            {anthropicSaved && (
              <div className="p-3 bg-green-100 text-green-700 rounded text-sm">
                ✓ Anthropic key saved successfully
              </div>
            )}
          </div>
        </div>

        {/* OpenAI API Key Section */}
        <div className="border rounded-lg p-6 bg-white shadow-sm">
          <h2 className="text-xl font-semibold mb-4">OpenAI API Key</h2>
          <p className="text-gray-600 text-sm mb-4">
            Get your API key from <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">platform.openai.com/api-keys</a>
          </p>
          
          <div className="space-y-3">
            <input
              type="password"
              value={openaiKey}
              onChange={(e) => setOpenaiKey(e.target.value)}
              placeholder="sk-..."
              className="w-full px-4 py-2 border rounded-lg font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            
            <div className="flex gap-3">
              <button
                onClick={handleSaveOpenaiKey}
                disabled={!openaiKey.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 font-medium"
              >
                Save Key
              </button>
              {openaiKey && (
                <button
                  onClick={handleClearOpenaiKey}
                  className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 font-medium"
                >
                  Clear
                </button>
              )}
            </div>

            {openaiSaved && (
              <div className="p-3 bg-green-100 text-green-700 rounded text-sm">
                ✓ OpenAI key saved successfully
              </div>
            )}
          </div>
        </div>

        {/* Privacy Note */}
        <div className="border-l-4 border-blue-500 bg-blue-50 p-4 rounded text-sm text-gray-700">
          <p className="font-semibold mb-2">🔒 Privacy & Security</p>
          <ul className="list-disc list-inside space-y-1">
            <li>Your API keys are stored only in your browser's cookies</li>
            <li>Keys are never transmitted to the server or stored on our servers</li>
            <li>You can clear keys at any time by clicking "Clear"</li>
            <li>Keys are never shared or logged</li>
          </ul>
        </div>
      </div>
      </div>
    </main>
  );
}
