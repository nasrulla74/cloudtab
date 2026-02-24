import client from "./client";

export async function login(email: string, password: string) {
  const res = await client.post("/auth/login", { email, password });
  return res.data;
}

export async function refreshToken(refresh_token: string) {
  const res = await client.post("/auth/refresh", { refresh_token });
  return res.data;
}

export async function getMe() {
  const res = await client.get("/users/me");
  return res.data;
}

export async function changePassword(currentPassword: string, newPassword: string) {
  await client.put("/users/me/password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}
