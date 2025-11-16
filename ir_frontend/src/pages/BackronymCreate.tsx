import React from 'react';
import Header from '../components/Header';

const BackronymCreate: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-100">
      <Header />
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-2xl mx-auto bg-white rounded-lg shadow-lg p-8 text-center">
          <h1 className="text-3xl font-bold text-gray-800 mb-4">Backronym Creation</h1>
          <p className="text-gray-600 mb-6">
            This page will be implemented in Phase 6
          </p>
          <p className="text-sm text-gray-500">
            Here you'll create backronyms for the given word
          </p>
        </div>
      </div>
    </div>
  );
};

export default BackronymCreate;
