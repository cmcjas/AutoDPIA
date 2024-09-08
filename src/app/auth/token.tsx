import { useState } from 'react';

function useToken() {

  function getToken() {
    const userToken = localStorage.getItem('token'); // Get the token from local storage
    return userToken && userToken
  }

  const [token, setToken] = useState(getToken());

  function saveToken(userToken: string) {
    localStorage.setItem('token', userToken); // Save the token to local storage
    setToken(userToken);
  };

  function removeToken() {
    localStorage.removeItem("token"); // Remove the token from local storage
    setToken(null);
  }

  return {
    setToken: saveToken,
    token,
    removeToken
  }

}

export default useToken;