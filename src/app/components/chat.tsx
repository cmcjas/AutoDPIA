'use client'

import Button from '@mui/material/Button';
import { useRef, useEffect, useState } from 'react'
import axios from 'axios';
import { TextField } from '@mui/material';
import {Box} from "@mui/material";

import SmartToyIcon from '@mui/icons-material/SmartToy';
import PersonIcon from '@mui/icons-material/Person';
import useToken from '../auth/token';


interface Message {
    sender: 'user' | 'bot';
    text: string;
}

export function Chat() {

    const [input, setInput] = useState('');
    const [file, setFile] = useState<File | null>(null);
    const [responses, setResponse] = useState<Message[]>([{ sender: 'bot', text: ' Hey there! I am here to help you with your DPIA. Please type your question below.' }]);

    const [fileName, setFileName] = useState<string>('');
    const [ragMode, setRagMode] = useState<boolean>(false);

    const chatParent = useRef<HTMLUListElement>(null)
    const { token, removeToken, setToken } = useToken();

    useEffect(() => {
        const domNode = chatParent.current
        if (domNode) {
            domNode.scrollTop = domNode.scrollHeight
        }
    })

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setInput(e.target.value);
    };

    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        if (event.target.files && event.target.files[0]) {
          setFile(event.target.files[0]);
        }
      };

    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (!input.trim()) {
            return;
        }

        const userMessage: Message = { sender: 'user', text: input };
        setResponse((prevMessages) => [...prevMessages, userMessage]);

        try {
            const res = await axios.post('http://localhost:8080/get_msg', 
                { 
                    message: input, 
                    ragMode: ragMode, 
                    fileName: fileName 
                },
                {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                }
            );

            const botMessage: Message = { sender: 'bot', text: res.data['reply'] };
            setResponse((prevMessages) => [...prevMessages, botMessage]);
            if (res.data.access_token) {
                const new_token = res.data.access_token
                setToken(new_token)
            }
        } catch (error) {
            console.error('Error:', error);
            const errorMessage: Message = { sender: 'bot', text: 'An error occurred while fetching the response.' };
            setResponse((prevMessages) => [...prevMessages, errorMessage]);
        } 
    };

    const clearSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        setInput('');
        setResponse([]);
        setResponse((prevMessages) => [...prevMessages, { sender: 'bot', text: ' Chat cleared successfully. I am now here to help you with your DPIA.' }]);

        try {
            const res = await axios.get('http://localhost:8080/clear_chat',
                {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                }
            );
            // if (res.data.access_token) {
            //     const new_token = res.data.access_token
            //     setToken(new_token)
            // }
        } catch (error) {
            console.error('Error:', error);
            const errorMessage: Message = { sender: 'bot', text: ' An error occurred while clearing the chat.' };
            setResponse((prevMessages) => [...prevMessages, errorMessage]);
        }
    };

    const docSubmit = async (event: React.FormEvent) => {
        event.preventDefault();
        if (!file) {
          alert('Please select a file first.');
          return;
        }
    
        const formData = new FormData();
        formData.append('File', file);
    
        try {
          const res = await axios.post('http://localhost:8080/upload_doc', formData, {
            headers: {
              'Content-Type': 'multipart/form-data',
              'Authorization': `Bearer ${token}`
            }
          });

          setFileName(res.data['filename']);
          setResponse((prevMessages) => [...prevMessages, { sender: 'bot', text: ` File uploaded successfully, I'm now your document assistant: ${res.data['filename']}` }]);
          setRagMode(true);
          if (res.data.access_token) {
            const new_token = res.data.access_token
            setToken(new_token)
            }

          console.log('File uploaded successfully');
        } catch (error) {
          console.error('Error uploading file', error);
        }
      };

    return (
        <main className="flex flex-col w-full h-screen max-h-dvh bg-background">

            <header className="p-4 border-b w-full h-16 bg-gradient-to-r from-purple-500 to-pink-500">
                <h1 className="text-3xl font-bold">CHAT</h1>
            </header>

            <section className="p-4 flex-1 overflow-auto" ref={chatParent}>
            <Box bgcolor="#e0e0e0" p={3} borderRadius={4} style={{ marginTop: '20px'}}>
                <ul className="flex flex-col w-full max-w-3xl mx-auto space-y-2">
                    {responses.map((message, index) => (
                        <li
                            key={index}
                            className={`text-primary ${message.sender === 'user' ? 'self-end text-right' : 'self-start text-left'}`}
                        >    
                            <span className={`inline-block p-2 rounded-lg ${message.sender === 'user' ? 'bg-blue-500 text-white' : 'bg-green-300 text-black'}`}>
                                {message.sender === 'bot' ? <SmartToyIcon fontSize='medium' /> : <PersonIcon fontSize='medium'/>}
                                {message.text}
                            </span>
                        </li>
                    ))}
                </ul>
            </Box>
            </section>


            <section>
                <form onSubmit={handleSubmit} className="flex w-full max-w-3xl mx-auto items-center">
                    <TextField className="flex-1 min-h-[40px] min-w-[50%]" variant="outlined" placeholder="Type your question here..." value={input} onChange={handleInputChange} />
                    <Button className="ml-2" type="submit" variant="contained" style={{marginLeft: '15px'}}>
                        Submit
                    </Button>
                </form>
                <form onSubmit={docSubmit} className="flex w-full max-w-3xl mx-auto items-center">
                    <input type="file" onChange={handleFileChange} accept=".txt,.docx,.pdf"/>
                    <Button className="ml-2" type="submit" variant="outlined">
                    Upload
                    </Button>
                </form>
                <form onSubmit={clearSubmit} className="flex w-full max-w-3xl mx-auto items-center">
                        <Button className="ml-2" type="submit" variant="outlined">
                            Clear
                        </Button>
                </form>
            </section>
        </main>
    )
}
