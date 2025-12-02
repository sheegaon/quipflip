import React from 'react';

const QFWelcomeInstructions: React.FC = () => (
  <>
    <h2 className="guest-welcome-title">How To Play</h2>

    <ul className="guest-welcome-list">
      <li>
        <strong>Quip:</strong> Write the original answer to a fill-in-the-blank prompt
      </li>
      <li>
        <strong>Impostor:</strong> Fake the original answer so it blends in with the real one
      </li>
      <li>
        <strong>Guess:</strong> Pick which answer you think was written first
      </li>
    </ul>

    <div className="guest-welcome-example">
      <strong>Example:</strong> In a Quip Round, you might answer "The best pizza topping is ______"
      with "peppers and mushrooms." In the Impostor Round (fake the original), other players will
      try to write similar answers without seeing the prompt. Guessers then try to pick which
      answer was the original.
    </div>
  </>
);

export default QFWelcomeInstructions;
