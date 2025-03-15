// HomeInterface.jsx
import { useState } from 'react';
import ChatInterface from './ChatInterface';
import ToolGenerator from './ToolGenerator';

const HomeInterface = () => {
  const [activeTab, setActiveTab] = useState('chat');

  return (
    <div className="flex flex-col h-screen bg-base-200">
      {/* Tabs */}
      <div className="tabs tabs-boxed bg-base-100 p-2 justify-center">
        <a 
          className={`tab ${activeTab === 'chat' ? 'tab-active' : ''}`}
          onClick={() => setActiveTab('chat')}
        >
          Chat
        </a>
        <a 
          className={`tab ${activeTab === 'tools' ? 'tab-active' : ''}`}
          onClick={() => setActiveTab('tools')}
        >
          Tool Generator
        </a>
      </div>
      
      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'chat' ? (
          <div className="h-full">
            <ChatInterface />
          </div>
        ) : (
          <div className="h-full">
            <ToolGenerator />
          </div>
        )}
      </div>
    </div>
  );
};

export default HomeInterface;