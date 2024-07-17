'use client'

import Button from '@mui/material/Button';
import { useRef, useEffect, useState } from 'react'
import axios from 'axios';
import { TextField } from '@mui/material';
import {Box} from "@mui/material";
import { styled } from '@mui/material/styles';

import SmartToyIcon from '@mui/icons-material/SmartToy';
import PersonIcon from '@mui/icons-material/Person';
import useToken from '../auth/token';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';


interface Message {
    sender: 'user' | 'bot';
    text: string;
    type?: 'text' | 'gif';
    src?: string;
    buttons?: { label: string, onClick: () => void, disabled?: boolean }[];
}

const VisuallyHiddenInput = styled('input')({
    clip: 'rect(0 0 0 0)',
    clipPath: 'inset(50%)',
    height: 1,
    overflow: 'hidden',
    position: 'absolute',
    bottom: 0,
    left: 0,
    whiteSpace: 'nowrap',
    width: 1,
  });

export function Chat() {

    const [input, setInput] = useState('');
    const [fetching, setFetching] = useState<boolean>(false);
    const [suggestions, setSuggestions] = useState<boolean>(false);

    const [responses, setResponse] = useState<Message[]>([{ 
        sender: 'bot', text: 'Hey there! I am here to help you with your DPIA. Please type your question below or choose from the following suggestions.', 
        buttons: [{ label: 'What is DPIA?', onClick: () => {setInput('What is DPIA?'), setSuggestions(true)} },
                  { label: 'What are the benefits of DPIA?', onClick: () => {setInput('What are the benefits of DPIA?'), setSuggestions(true)} },
                  { label: 'What are the risks of DPIA?', onClick: () => {setInput('What are the risks of DPIA?'), setSuggestions(true)} },
                  { label: 'What are the steps to perform DPIA?', onClick: () => {setInput('What are the steps to perform DPIA?'), setSuggestions(true)} },
                  { label: 'What are the legal requirements for DPIA?', onClick: () => {setInput('What are the legal requirements for DPIA?'), setSuggestions(true)} },
                  { label: 'What are the best practices for DPIA?', onClick: () => {setInput('What are the best practices for DPIA?'), setSuggestions(true)} },
                  { label: 'How to generate a DPIA in AutoDPIA?', onClick: () => {setInput('How to generate a DPIA in AutoDPIA?'), setSuggestions(true)} },
                  { label: 'CHAT, TEMPLATE and PROJECT in AutoDPIA', onClick: () => {setInput('CHAT, TEMPLATE and PROJECT in AutoDPIA'), setSuggestions(true)} }],
        }]);
    const [fileName, setFileName] = useState<string>('');
    const [pdfMode, setPdfMode] = useState<boolean>(false);

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

    const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
        let File
        if (event.target.files && event.target.files[0]) {
          File = event.target.files[0]
        }

        if (!File) {
          alert('Please select a file first.');
          return;
        }

        const formData = new FormData();
        formData.append('File', File);

        try {
          const res = await axios.post('http://localhost:8080/upload_doc', formData, {
            headers: {
              'Content-Type': 'multipart/form-data',
              'Authorization': `Bearer ${token}`
            }
          });

          setFileName(res.data['filename']);
          setResponse([{ sender: 'bot', text: `File uploaded successfully, I'm now your document assistant on: ${res.data['filename']}`,
            buttons: [{ label: 'What is the document about?', onClick: () => {setInput('What is the document about?'), setSuggestions(true)} },
                { label: 'What is the document implication for conducting a DPIA?', onClick: () => {setInput('What is the document implication for conducting a DPIA?'), setSuggestions(true)}},
                { label: 'Any potential sensitive information?', onClick: () => {setInput('Any potential sensitive information?'), setSuggestions(true)} }], 
          }]);
          setPdfMode(true);
          if (res.data.access_token) {
            const new_token = res.data.access_token
            setToken(new_token)
            }
          event.target.value = ''; // clear the input after uploading

        } catch (error) {
          console.error('Error uploading file', error);
        }
        
    };

    /* randomly select a message */
    const messages = [
        "I hope this has been helpful to you. If you have any more questions, feel free to ask.",
        "Is there anything else I can assist you with today?",
        "Feel free to reach out if you have more questions.",
        "I'm here to help if you need anything else.",
        "I hope you find this helpful. Click 'CLEAR' to start anew.",
    ];
    
    const getRandomMessage = () => {
        return messages[Math.floor(Math.random() * messages.length)];
    };

    const fetchMessage = async () => {
        try {
            setResponse((prevMessages) => [
                ...prevMessages,
                { sender: 'bot', text:'', type: 'gif', src: '/loading-gif.gif' }
            ]);

            const tempInput = input;

            const res = await axios.post('http://localhost:8080/get_msg', 
                { 
                    message: input, 
                    pdfMode: pdfMode, 
                    fileName: fileName 
                },
                {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                }
            );

            setFetching(false);
            // Remove the first loading gif from the response
            setResponse((prevMessages) => {
                const index = prevMessages.findIndex(message => message.type === 'gif');
                if (index !== -1) {
                    return [
                        ...prevMessages.slice(0, index),
                        ...prevMessages.slice(index + 1),
                    ];
                }
                return prevMessages;
            });
            
            const botMessage: Message = { sender: 'bot', text: res.data['reply'] };
            setResponse((prevMessages) => [...prevMessages, botMessage]);

            responses.map((message) => { console.log(message.text) });

            if (tempInput === 'What is DPIA?') {
                setResponse((prevMessages) => [...prevMessages, { sender: 'bot', text: "You may find the following suggestions helpful.",
                    buttons: [{ label: 'How to perform DPIA?', onClick: () => {setInput('How to perform DPIA?'), setSuggestions(true)} },
                        { label: 'What are the benefits of DPIA?', onClick: () => {setInput('What are the benefits of DPIA?'), setSuggestions(true)}},
                        { label: 'The role of a DPO', onClick: () => {setInput('The role of a DPO'), setSuggestions(true)} }],
                }]);
            } else if (tempInput === 'What are the steps to perform DPIA?') {
                setResponse((prevMessages) => [...prevMessages, { sender: 'bot', text: "You may find the following suggestions helpful.",
                    buttons: [{ label: 'What are the risks of DPIA?', onClick: () => {setInput('What are the risks of DPIA?'), setSuggestions(true)} },
                        { label: 'How to identify risks and their solutions?', onClick: () => {setInput('How to identify risks and their solutions?'), setSuggestions(true)}},
                        { label: '3x3 Risk Matrix', onClick: () => {setInput('3x3 Risk Matrix'), setSuggestions(true)} }],
                }]);
            } else if (tempInput === 'CHAT, TEMPLATE and PROJECT in AutoDPIA') {
                setResponse((prevMessages) => [...prevMessages, { sender: 'bot', text: "You may find the following suggestions helpful.",
                    buttons: [{ label: 'What is CHAT PDF mode?', onClick: () => {setInput('What is CHAT PDF mode?'), setSuggestions(true)} },
                        { label: 'How to access TEMPLATE and PROJECT to produce a DPIA?', onClick: () => {setInput('How to access TEMPLATE and PROJECT to produce a DPIA?'), setSuggestions(true)} }],
                }]);
            } else if (tempInput === 'What is the document about?') {
                setResponse((prevMessages) => [...prevMessages, { sender: 'bot', text: "You may find the following suggestions helpful.",
                    buttons: [{ label: 'How many tables and images in the document?', onClick: () => {setInput('How many tables and images in the document?'), setSuggestions(true)} }],
                }]);
            } else if (tempInput === 'What is the document implication for conducting a DPIA?') {
                setResponse((prevMessages) => [...prevMessages, { sender: 'bot', text: "You may find the following suggestions helpful.",
                    buttons: [{ label: 'What are the potential risks and solutions?', onClick: () => {setInput('What are the potential risks and solutions?'), setSuggestions(true)} }],
                }]);
            } else {
                setResponse((prevMessages) => [...prevMessages, { sender: 'bot', text: getRandomMessage() }]);
            }

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

    if (suggestions) {
        if (!pdfMode) {
            setResponse((prevMessages) => [...prevMessages,
                { sender: 'bot', text:`Great! Let's explore: ${input}`}
            ]);
        } else {
            setResponse(
                (prevMessages) => [...prevMessages, { sender: 'bot', text:`Let's investigate the document further via: ${input}`}
            ]);
        }

        fetchMessage();
        setInput('');
        setSuggestions(false);
        setFetching(true);
    }

    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (!input.trim()) {
            return;
        }

        const userMessage: Message = { sender: 'user', text: input };
        setResponse((prevMessages) => [...prevMessages, userMessage]);

        setFetching(true);
        fetchMessage();
    };


    const clearSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        setInput('');
        setResponse([]);
        setPdfMode(false);
        setResponse((prevMessages) => [...prevMessages, { sender: 'bot', text: ' Chat cleared successfully. I am here to help you with your DPIA. Please type your question below or choose from the following suggestions.',
            buttons: [{ label: 'What is DPIA?', onClick: () => {setInput('What is DPIA?'), setSuggestions(true)} },
                { label: 'What are the benefits of DPIA?', onClick: () => {setInput('What are the benefits of DPIA?'), setSuggestions(true)}},
                { label: 'What are the risks of DPIA?', onClick: () => {setInput('What are the risks of DPIA?'), setSuggestions(true)} },
                { label: 'What are the steps to perform DPIA?', onClick: () => {setInput('What are the steps to perform DPIA?'), setSuggestions(true)}},
                { label: 'What are the legal requirements for DPIA?', onClick: () => {setInput('What are the legal requirements for DPIA?'), setSuggestions(true)} },
                { label: 'What are the best practices for DPIA?', onClick: () => {setInput('What are the best practices for DPIA?'), setSuggestions(true)} },
                { label: 'How to generate a DPIA in AutoDPIA?', onClick: () => {setInput('How to generate a DPIA in AutoDPIA?'), setSuggestions(true)} },
                { label: 'CHAT, TEMPLATE and PROJECT in AutoDPIA', onClick: () => {setInput('CHAT, TEMPLATE and PROJECT in AutoDPIA'), setSuggestions(true)} }],
      }]);

        try {
            const res = await axios.get('http://localhost:8080/clear_chat',
                {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                }
            );
            if (res.data.access_token) {
                const new_token = res.data.access_token
                setToken(new_token)
            }
        } catch (error) {
            console.error('Error:', error);
            const errorMessage: Message = { sender: 'bot', text: ' An error occurred while clearing the chat.' };
            setResponse((prevMessages) => [...prevMessages, errorMessage]);
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
                            <span className={`inline-block p-2 rounded-lg ${message.sender === 'user' ? 'bg-blue-500 text-white' : 'bg-green-300 text-black'} whitespace-pre-wrap`}>
                                {message.sender === 'bot' ? (<><SmartToyIcon fontSize='medium' /> </>) : (<><PersonIcon fontSize='medium'/> </>)}
                                {message.type === 'gif' ? (
                                    <img src={message.src} alt="GIF" style={{width:'30px', height:'30px'}}/>
                                ) : (
                                    message.text
                                )}
                            </span>
                            {message.buttons && (
                            <div className="mt-2">
                                {message.buttons.map((button, idx) => (
                                <Button
                                    key={idx}
                                    onClick={button.onClick}
                                    className="bg-blue-500 text-white p-2 rounded-lg m-1"
                                    disabled={fetching}
                                    variant="contained"
                                    color="secondary"
                                    style={{marginLeft: '10px', marginBottom: '10px'}}
                                >
                                    {button.label}
                                </Button>
                                ))}
                            </div>
                            )}
                        </li>
                    ))}
                </ul>
            </Box>
            </section>


            <section style={{marginBottom: '15px'}}>
                <form onSubmit={handleSubmit} className="flex w-full max-w-3xl mx-auto items-center">
                    <TextField className="flex-1 min-h-[40px] min-w-[50%]" variant="outlined" placeholder="Type your question here..." value={input} onChange={handleInputChange} disabled={fetching}/>
                    <Button className="ml-2" type="submit" variant="contained" style={{marginLeft: '15px'}} disabled={fetching}>
                        Submit
                    </Button>
                </form>
                <div className="flex w-full max-w-3xl mx-auto items-center" style={{ marginTop:'10px', marginBottom:'5px'}}>
                    <Button
                        component="label"
                        variant="contained"
                        color="success"
                        tabIndex={-1}
                        startIcon={<CloudUploadIcon />}
                        style={{marginLeft: '10px', marginRight: '15px'}}
                    >
                        Upload
                        <VisuallyHiddenInput type="file" onChange={handleFileChange} accept=".txt,.docx,.pdf" />
                    </Button>
                    <form onSubmit={clearSubmit} className="flex w-full max-w-3xl mx-auto items-center">
                            <Button className="ml-2" type="submit" variant="outlined">
                                Clear
                            </Button>
                    </form>
                </div>
            </section>
        </main>
    )
}
