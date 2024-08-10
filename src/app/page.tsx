'use client';

import { useEffect, useState } from 'react';
import Chat from "./components/chat";
import Project from "./components/project";
import Template from "./components/temp";
import { Button } from "@mui/material";
import Metric from './components/metric';
import  Login  from "./auth/login";
import  Register  from "./auth/register";
import axios from 'axios';
import useToken from "./auth/token";

import Image from 'next/image';
import AutoDPIA_transparent from '/public/AutoDPIA_transparent.png';

export const runtime = 'edge';

export default function Page() {
  const [selectedComponent, setSelectedComponent] = useState<'chat' | 'temp' | 'project'>('chat');
  const { token, removeToken, setToken } = useToken();
  const [login, setLogin] = useState(false);
  const [email, setEmail] = useState<string>('');


  const handleRegister = () => {
    setLogin(true);
  }

  useEffect(() => {
    const savedEmail = localStorage.getItem('email');
    if (savedEmail) {
      setEmail(savedEmail);
    }

    // Check if the token exists before setting up the interval
    if (token) {
      // Set up the interval to call refreshToken every 30 minutes
      const intervalId = setInterval(() => {
        refreshToken();
      }, 30 * 60 * 1000); // 30 minutes in milliseconds

      // Cleanup the interval on component unmount
      return () => clearInterval(intervalId);
    }
  }, [token]);


  if (!token && !login)  {
    return (
      <div className="h-16 bg-gradient-to-r from-purple-500 to-pink-500">
      <div style={{ display: 'flex', height: '100vh', justifyContent: 'center', alignItems: 'center' }}>
        <div>
          <Login setToken={setToken} setEmail={setEmail} />
        <div style={{ marginTop: '15px' }}>
          <Button color='secondary' onClick={handleRegister}>Don't have an account? Register here.</Button>
        </div>
        </div>
      </div>
      </div>
    )
  }

  if (!token && login) {
    return (
      <div className="h-16 bg-gradient-to-r from-purple-500 to-pink-500">
      <div style={{ display: 'flex', height: '100vh', justifyContent: 'center', alignItems: 'center' }}>
        <div>
        <Register setLogin={setLogin} />
        </div>
      </div>
      </div>
    )
  }

  const refreshToken = async () => {
    
    const res = await axios.get('http://localhost:8080/refresh_token',{
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });
    if (res.data.access_token) {
      setToken(res.data.access_token);
    }
  }


  const handleLogout = async () => {
    const res = await axios.post('http://localhost:8080/logout');
    // Clear any client-side authentication data (e.g., localStorage)
    setSelectedComponent('chat');
    if (res) {
      removeToken();
    }
  };

  return (
    <div style={{ display: 'flex', height: '100vh' }}>
      <div style={{ width: '30vh', borderRight: '1px solid #ccc', padding: '10px' }}>
        <header className="p-4 border-b w-full max-w-3xl mx-auto" style={{ display: 'flex', alignItems: 'center' }}>
          <h1 className="text-3xl font-bold ">AutoDPIA</h1>
          <Image src={AutoDPIA_transparent} alt="AutoDPIA Logo" width={40} height={40} style={{marginLeft: '10px'}}/>
        </header>
        
        <div style={{ display: 'flex', flexDirection: 'column', marginTop: '20px', height: '85vh' }}>
          <Button color='secondary' onClick={() => setSelectedComponent('chat')} style={{ marginBottom: '20px', backgroundColor: selectedComponent === 'chat' ? '#1c5b99' : 'transparent',
                     color: selectedComponent === 'chat' ? 'white' : 'black' }} variant="outlined"><h1 className="text-1xl font-bold ">Chat</h1></Button>
          <Button color='secondary' onClick={() => setSelectedComponent('temp')} style={{ marginBottom: '20px', backgroundColor: selectedComponent === 'temp' ? '#1c5b99' : 'transparent',
                      color: selectedComponent === 'temp' ? 'white' : 'black' }} variant="outlined"><h1 className="text-1xl font-bold ">Template</h1></Button>
          <Button color='secondary' onClick={() => setSelectedComponent('project') } style={{backgroundColor: selectedComponent === 'project' ? '#1c5b99' : 'transparent',
                      color: selectedComponent === 'project' ? 'white' : 'black' }}variant="outlined"><h1 className="text-1xl font-bold ">Project</h1></Button>
          <div style={{ flexGrow: 1 }}></div>
          <Metric token={token} /> 
          <div style={{ flexGrow: 1 }}></div> 
          <h1 className="text-1xl font-bold " >WELCOME:  <span style={{ marginLeft: '5px' }}>{email}</span></h1>
          <Button onClick={handleLogout} color='secondary' variant="contained" style={{marginTop:'10px'}}>Logout</Button>
        </div>
      </div>

      <div style={{ flex: 1, padding: '10px' }}>
        <div style={{ display: selectedComponent === 'chat' ? 'block' : 'none' }}>
          <Chat token={token}/>
        </div>
        <div style={{ display: selectedComponent === 'temp' ? 'block' : 'none' }}>
          <Template token={token}/>
        </div>
        <div style={{ display: selectedComponent === 'project' ? 'block' : 'none' }}>
          <Project token={token} />
        </div>
      </div>
      </div>
  );

}