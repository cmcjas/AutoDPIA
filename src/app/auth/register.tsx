import { useState } from 'react';
import { Button, TextField } from "@mui/material";
import axios from 'axios';
import Image from 'next/image';
import AutoDPIA_transparent from '/public/AutoDPIA_transparent.png';

type LoginProps = {
  setLogin: (login: boolean) => void;
};


const Register = (props: LoginProps) => {

  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState('');
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');
  const [login, setLogin] = useState(false);

  const handleLogin = () => {
    props.setLogin(false);
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    try {
      const res = await axios.post('http://localhost:8080/register', {
        email,
        password
      });  // Important to include credentials for session cookie
      setSuccess('Registration successful! Please login.');
      setError('');
    } catch (error) {
      setError('Registration failed. Email might already be in use');
      setSuccess('');
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
          onChange={(e) => setEmail(e.target.value)}
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
        {success && <div style={{ color: 'green', marginTop: '10px' }}>{success}</div>}
        <Button type="submit" variant="contained" color="primary" style={{ marginTop: '20px' }}>
          Register
        </Button>
        <Button type="submit" variant="contained" color="primary" onClick={handleLogin} style={{ marginTop: '10px' }}>
          Back
        </Button> 
      </form>
    )}

export default Register;