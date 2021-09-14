import { combineReducers } from "@reduxjs/toolkit";
import { HYDRATE } from "next-redux-wrapper";
import userReducer from "./user";
import loginReducer from "./login";
import signupReducer from "./signup";
import storage from "redux-persist/lib/storage";

export const persistConfig = {
  key: "root",
  storage,
};

export const combinedReducers = combineReducers({
  user: userReducer,
  login: loginReducer,
  signup: signupReducer,
});

const rootReducer = (state, action) => {
  if (action.type === HYDRATE) {
    const nextState = {
      ...state,
      ...action.payload,
    };
    return nextState;
  }
  return combinedReducers(state, action);
};

export default rootReducer;
