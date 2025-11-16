import React from 'react';
import { useParams } from 'react-router-dom';
import Header from '../components/Header';

const Voting: React.FC = () => {
  const { setId } = useParams<{ setId: string }>();

  return (
    <div className="min-h-screen bg-gray-100">
      <Header />
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-2xl mx-auto bg-white rounded-lg shadow-lg p-8 text-center">
          <h1 className="text-3xl font-bold text-gray-800 mb-4">Voting</h1>
          <p className="text-gray-600 mb-6">
            This page will be implemented in Phase 6
          </p>
          <p className="text-sm text-gray-500">
            Set ID: {setId}
          </p>
          <p className="text-sm text-gray-500 mt-2">
            Here you'll vote for the best backronym
          </p>
        </div>
      </div>
    </div>
  );
};

export default Voting;
