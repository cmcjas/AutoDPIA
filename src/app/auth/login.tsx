import { useState, useEffect } from 'react';
import { Button, TextField } from "@mui/material";
import axios from 'axios';
import Image from 'next/image';
import AutoDPIA_transparent from '/public/AutoDPIA_transparent.png';



type LoginProps = {
  setToken: (token: string) => void;
  setEmail: (email: string) => void;
};

const Login = (props: LoginProps) => {

  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setEmail(e.target.value);
    localStorage.setItem('email', e.target.value);
  };


  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    try {
      const res = await axios.post('http://localhost:8080/login', {
        email,
        password
      });  
      props.setToken(res.data.access_token)
      props.setEmail(email)
    } catch (error) {
      console.log('Error:', error);
      setError('Invalid user email or password');
    }
  };

  return (
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', width: '300px' }}>
        <header className="p-4 w-full max-w-3xl mx-auto" style={{ display: 'flex', alignItems: 'center' }}>
          <h1 className="text-3xl font-bold ">AutoDPIA</h1>
          <Image src={AutoDPIA_transparent} alt="AutoDPIA Logo" width={40} height={40} style={{marginLeft: '10px'}}/>
        </header>
        
        <TextField
          label="Email"
          value={email}
          onChange={handleEmailChange}
          required
          margin="normal"
        />
        <TextField
          label="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          margin="normal"
        />
        {error && <div style={{ color: 'red', marginTop: '10px' }}>{error}</div>}
        <Button type="submit" variant="contained" color="primary" style={{ marginTop: '20px' }}>
          Login
        </Button>
      </form>
  );
};


export default Login;

