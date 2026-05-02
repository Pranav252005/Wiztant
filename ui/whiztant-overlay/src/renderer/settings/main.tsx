import React from 'react';
import ReactDOM from 'react-dom/client';
import Settings from './Settings';
import '../shared/types';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Settings onBack={() => {}} />
  </React.StrictMode>,
);
