export type SurveyQuestionType = 'scale' | 'single' | 'multi' | 'text' | 'compound';

export interface SurveyOption<T extends string | number = string> {
  value: T;
  label: string;
}

interface SurveyQuestionBase {
  id: string;
  title: string;
  description?: string;
  required?: boolean;
}

export interface ScaleSurveyQuestion extends SurveyQuestionBase {
  type: 'scale';
  options: SurveyOption<number>[];
}

export interface SingleSurveyQuestion extends SurveyQuestionBase {
  type: 'single';
  options: SurveyOption<string>[];
}

export interface MultiSurveyQuestion extends SurveyQuestionBase {
  type: 'multi';
  options: SurveyOption<string>[];
}

export interface TextSurveyQuestion extends SurveyQuestionBase {
  type: 'text';
  placeholder?: string;
  maxLength?: number;
}

export interface CompoundSurveyQuestion extends SurveyQuestionBase {
  type: 'compound';
  primary: SingleSurveyQuestion;
  followUp: TextSurveyQuestion;
}

export type SurveyQuestion =
  | ScaleSurveyQuestion
  | SingleSurveyQuestion
  | MultiSurveyQuestion
  | TextSurveyQuestion
  | CompoundSurveyQuestion;

export interface SurveySection {
  id: string;
  title: string;
  questions: SurveyQuestion[];
}

export interface SurveyDefinition {
  id: string;
  title: string;
  description?: string;
  sections: SurveySection[];
  requiredQuestionIds: string[];
}
