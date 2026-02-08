import axios from 'axios';

// 集成到客户端时设 REACT_APP_API_URL= 留空则同源；未设则开发时默认 localhost:8000
const API_URL = process.env.REACT_APP_API_URL !== undefined ? process.env.REACT_APP_API_URL : 'http://localhost:8000';

const client = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export default client;
