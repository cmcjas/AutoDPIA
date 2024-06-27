'use client';

import { Chat } from "./components/chat";
import { Project } from "./components/project";
import { Template } from "./components/temp";
import { useState } from 'react';
import { Button } from "@mui/material";

export const runtime = 'edge';

export default function Page() {
  const [selectedComponent, setSelectedComponent] = useState<'chat' | 'temp' | 'project'>('chat');

  return (
    <div style={{ display: 'flex', height: '100vh' }}>
      <div style={{ width: '30vh', borderRight: '1px solid #ccc', padding: '10px' }}>
        <header className="p-4 border-b w-full max-w-3xl mx-auto">
          <h1 className="text-3xl font-bold">AutoDPIA</h1>
        </header>

        <div style={{ display: 'flex', flexDirection: 'column', marginTop: '20px' }}>
          <Button onClick={() => setSelectedComponent('chat')} style={{ marginBottom: '20px', backgroundColor: selectedComponent === 'chat' ? '#1976d2' : 'transparent',
                     color: selectedComponent === 'chat' ? 'white' : 'black' }} variant="outlined">Chat</Button>
          <Button onClick={() => setSelectedComponent('temp')} style={{ marginBottom: '20px', backgroundColor: selectedComponent === 'temp' ? '#1976d2' : 'transparent',
                      color: selectedComponent === 'temp' ? 'white' : 'black' }} variant="outlined">Template</Button>
          <Button onClick={() => setSelectedComponent('project') } style={{backgroundColor: selectedComponent === 'project' ? '#1976d2' : 'transparent',
                      color: selectedComponent === 'project' ? 'white' : 'black' }}variant="outlined">Generate DPIA</Button>
        </div>
      </div>
      <div style={{ flex: 1, padding: '10px' }}>
        <div style={{ display: selectedComponent === 'chat' ? 'block' : 'none' }}>
          <Chat />
        </div>
        <div style={{ display: selectedComponent === 'temp' ? 'block' : 'none' }}>
          <Template />
        </div>
        <div style={{ display: selectedComponent === 'project' ? 'block' : 'none' }}>
          <Project />
        </div>
      </div>
    </div>
  );

}