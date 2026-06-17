# BoxIM SDK 参考文档

## 核心概念

BoxIM 是一个即时通讯 SDK，所有功能通过 `BoxIM` 类实例访问。**始终通过 `boxim.client` 模块使用全局单例，禁止直接实例化 `BoxIM`。**

---

## 初始化（必读）

```python
from boxim.client import initialize_im_client, get_im_client

# 首次初始化（幂等，重复调用不会重新登录）
im = initialize_im_client("username", "password")

# 在任意位置获取已初始化的客户端
im = get_im_client()
```

`initialize_im_client(username, password)` — 初始化全局单例并登录，已初始化则直接返回现有实例，返回 `BoxIM`。

`get_im_client()` — 获取已初始化的全局单例，未初始化时抛出 `RuntimeError`。

---

## 认证

`im.login(username, password, terminal)` — 同步登录，返回 `self`，支持链式调用。`terminal` 默认 `TerminalType.WEB`。

`await im.alogin(username, password, terminal)` — 异步登录，返回 `self`。

`im.register(mode, user_name, phone, email, code, password, confirm_password, nick_name)` — 注册用户。`mode` 为 `RegistrationMode.USERNAME/PHONE/EMAIL`，对应模式必须提供相应字段，否则抛出 `ValidationError`。返回 `Dict`。

`await im.aregister(...)` — 异步注册。

`im.refresh_token()` — 刷新访问令牌，需已登录，无刷新令牌时抛出 `AuthError`，返回 `self`。

`await im.arefresh_token()` — 异步刷新令牌。

`im.modify_password(old_password, new_password)` — 修改密码，需已登录，返回 `Dict`。

`await im.amodify_password(old_password, new_password)` — 异步修改密码。

`im.reset_password(mode, phone, email, code, password, confirm_password)` — 通过手机或邮箱验证码重置密码，无需登录，返回 `Dict`。

`await im.areset_password(...)` — 异步重置密码。

---

## 二维码登录

`im.generate_qr_login()` — 生成二维码登录信息，返回 `QRLoginInfo`（含 `qr_code`、`qr_image` base64、`expires_in`）。

`await im.agenerate_qr_login()` — 异步生成。

`im.check_qr_login_status(qr_code)` — 查询二维码状态，返回 `Dict`，确认后含 `accessToken`。

`await im.acheck_qr_login_status(qr_code)` — 异步查询。

`im.qr_login_wait(poll_interval=2.0, timeout=300.0)` — 自动生成二维码并轮询等待扫码确认，超时或过期抛出 `AuthError`，返回 `self`。

`await im.aqr_login_wait(poll_interval=2.0, timeout=300.0)` — 异步轮询等待。

---

## 用户

`im.get_me()` — 获取当前登录用户信息，返回 `Dict`。

`await im.aget_me()` — 异步获取。

`im.me` — 属性，等同于调用 `get_me()`，返回 `Dict`。

`im.get_user(user_id)` — 按 ID 获取用户，返回 `User`。

`await im.aget_user(user_id)` — 异步获取。

`im.search_users(keyword)` — 按关键词搜索用户（ID/昵称/手机/邮箱），返回 `List[User]`。

`await im.asearch_users(keyword)` — 异步搜索。

`im.update_profile(**kwargs)` — 更新当前用户资料，`kwargs` 可含 `nickName`、`sex`、`signature`、`headImage` 等字段，返回 `self`。

`await im.aupdate_profile(**kwargs)` — 异步更新。

`im.get_online_terminals(user_ids)` — 获取用户在线终端，`user_ids` 为单个 `int` 或 `List[int]`，返回 `List[Dict]`。

`await im.aget_online_terminals(user_ids)` — 异步获取。

---

## 好友

`im.get_friends()` — 获取好友列表，返回 `List[Friend]`。

`await im.aget_friends()` — 异步获取。

`im.friends` — 属性，等同于 `get_friends()`。

`im.get_friend_info(user_id)` — 获取指定好友信息，返回 `Friend`。

`await im.aget_friend_info(user_id)` — 异步获取。

`im.add_friend(user_id, remark=None)` — 发送好友请求，返回 `self`。

`await im.aadd_friend(user_id, remark=None)` — 异步发送。

`im.send_friend_request(user_id, message=None)` — `add_friend` 的别名，返回 `self`。

`await im.asend_friend_request(user_id, message=None)` — 异步别名。

`im.delete_friend(user_id)` — 删除好友，返回 `self`。

`await im.adelete_friend(user_id)` — 异步删除。

`im.set_friend_dnd(user_id, dnd)` — 设置好友免打扰，`dnd` 为 `bool`，返回 `self`。

`await im.aset_friend_dnd(user_id, dnd)` — 异步设置。

`im.set_friend_top(user_id, top)` — 设置好友置顶，返回 `self`。

`await im.aset_friend_top(user_id, top)` — 异步设置。

`im.update_friend_remark(user_id, remark)` — 更新好友备注名，返回 `self`。

`await im.aupdate_friend_remark(user_id, remark)` — 异步更新。

---

## 好友请求

`im.get_friend_requests()` — 获取待处理好友请求列表，返回 `List[FriendRequest]`。

`await im.aget_friend_requests()` — 异步获取。

`im.friend_requests` — 属性，等同于 `get_friend_requests()`。

`im.accept_friend_request(request_id)` — 接受好友请求，返回 `self`。

`await im.aaccept_friend_request(request_id)` — 异步接受。

`im.reject_friend_request(request_id)` — 拒绝好友请求，返回 `self`。

`await im.areject_friend_request(request_id)` — 异步拒绝。

`im.recall_friend_request(request_id)` — 撤回自己发出的好友请求，返回 `self`。

`await im.arecall_friend_request(request_id)` — 异步撤回。

---

## 黑名单

`im.add_to_blacklist(user_id)` — 拉黑用户，返回 `self`。

`await im.aadd_to_blacklist(user_id)` — 异步拉黑。

`im.remove_from_blacklist(user_id)` — 移出黑名单，返回 `self`。

`await im.aremove_from_blacklist(user_id)` — 异步移出。

`im.get_blacklist()` — 获取黑名单列表，返回 `List[User]`。

`await im.aget_blacklist()` — 异步获取。

---

## 群组

`im.get_groups()` — 获取已加入的群组列表，返回 `List[Group]`。

`await im.aget_groups()` — 异步获取。

`im.groups` — 属性，等同于 `get_groups()`。

`im.create_group(name, member_ids)` — 创建群组，`member_ids` 为初始成员 ID 列表，返回 `Group`。

`await im.acreate_group(name, member_ids)` — 异步创建。

`im.get_group_info(group_id)` — 获取群组详情，返回 `Group`。

`await im.aget_group_info(group_id)` — 异步获取。

`im.modify_group(group_id, **kwargs)` — 修改群组信息，`kwargs` 可含 `name`、`notice`、`headImage`、`remarkGroupName` 等，返回 `self`。

`await im.amodify_group(group_id, **kwargs)` — 异步修改。

`im.delete_group(group_id)` — 解散群组（仅群主），返回 `self`。

`await im.adelete_group(group_id)` — 异步解散。

`im.quit_group(group_id)` — 退出群组（群主不可用），返回 `self`。

`await im.aquit_group(group_id)` — 异步退出。

`im.get_group_members(group_id, version=0)` — 获取群成员列表，`version` 用于增量更新，返回 `List[User]`。

`await im.aget_group_members(group_id, version=0)` — 异步获取。

`im.get_group_online_members(group_id)` — 获取在线成员 ID 列表，返回 `List[int]`。

`await im.aget_group_online_members(group_id)` — 异步获取。

`im.invite_to_group(group_id, user_ids)` — 邀请成员入群，`user_ids` 为 ID 列表，返回 `self`。

`await im.ainvite_to_group(group_id, user_ids)` — 异步邀请。

`im.remove_group_members(group_id, user_ids)` — 踢出成员，返回 `self`。

`await im.aremove_group_members(group_id, user_ids)` — 异步踢出。

`im.join_group(group_id, token=None)` — 申请加入群组，`token` 为群名片 token（可选），返回 `self`。

`await im.ajoin_group(group_id, token=None)` — 异步申请。

`im.get_group_card_token(group_id)` — 获取群名片分享 token，返回 `str`。

`await im.aget_group_card_token(group_id)` — 异步获取。

`im.set_group_dnd(group_id, dnd)` — 设置群组免打扰，返回 `self`。

`await im.aset_group_dnd(group_id, dnd)` — 异步设置。

`im.set_group_top(group_id, top)` — 设置群组置顶，返回 `self`。

`await im.aset_group_top(group_id, top)` — 异步设置。

`im.set_group_muted(group_id, muted)` — 全员禁言，返回 `self`。

`await im.aset_group_muted(group_id, muted)` — 异步设置。

`im.set_group_allow_invite(group_id, allow)` — 设置是否允许成员邀请他人，返回 `self`。

`await im.aset_group_allow_invite(group_id, allow)` — 异步设置。

`im.set_group_allow_share_card(group_id, allow)` — 设置是否允许分享群名片，返回 `self`。

`await im.aset_group_allow_share_card(group_id, allow)` — 异步设置。

`im.set_group_member_muted(group_id, user_ids, muted)` — 设置指定成员禁言，`user_ids` 为单个 `int` 或列表，返回 `self`。

`await im.aset_group_member_muted(group_id, user_ids, muted)` — 异步设置。

`im.add_group_manager(group_id, user_ids)` — 添加管理员（仅群主），`user_ids` 为单个 `int` 或列表，返回 `self`。

`await im.aadd_group_manager(group_id, user_ids)` — 异步添加。

`im.remove_group_manager(group_id, user_ids)` — 移除管理员（仅群主），返回 `self`。

`await im.aremove_group_manager(group_id, user_ids)` — 异步移除。

`im.set_group_top_message(group_id, message_id)` — 设置群置顶消息，返回 `self`。

`await im.aset_group_top_message(group_id, message_id)` — 异步设置。

`im.remove_group_top_message(group_id)` — 移除群置顶消息，返回 `self`。

`await im.aremove_group_top_message(group_id)` — 异步移除。

`im.hide_group_top_message(group_id)` — 仅对自己隐藏置顶消息，返回 `self`。

`await im.ahide_group_top_message(group_id)` — 异步隐藏。

---

## 私聊消息

所有发送方法需已登录，返回 `self` 支持链式调用。

`im.send_text(user_id, text)` — 发送文本消息。

`await im.asend_text(user_id, text)` — 异步发送。

`im.send_image(user_id, image_path)` — 上传本地图片并发送。

`await im.asend_image(user_id, image_path)` — 异步发送。

`im.send_file(user_id, file_path)` — 上传本地文件并发送。

`await im.asend_file(user_id, file_path)` — 异步发送。

`im.send_voice(user_id, voice_path, duration=3)` — 上传语音文件并发送，`duration` 为秒数。

`await im.asend_voice(user_id, voice_path, duration=3)` — 异步发送。

`im.send_video(user_id, video_path)` — 上传视频并发送。

`await im.asend_video(user_id, video_path)` — 异步发送。

`im.send_sticker(user_id, sticker_id)` — 发送贴纸，`sticker_id` 为贴纸 ID。

`await im.asend_sticker(user_id, sticker_id)` — 异步发送。

`im.send_user_card(user_id, target_user_id, target_nickname, target_head_image)` — 发送个人名片。

`await im.asend_user_card(...)` — 异步发送。

`im.send_group_card(user_id, group_id, group_name, group_head_image)` — 发送群聊名片。

`await im.asend_group_card(...)` — 异步发送。

`im.send_private_raw(user_id, content, msg_type, receipt=False, quote_message_id=None)` — 发送原始私聊消息，完全控制内容和类型，`msg_type` 为 `MessageType` 枚举，返回 `Dict`。

`await im.asend_private_raw(...)` — 异步发送。

`im.recall_private_message(message_id)` — 撤回私聊消息，返回 `self`。

`await im.arecall_private_message(message_id)` — 异步撤回。

`im.mark_private_read(friend_id)` — 标记与某好友的私聊消息为已读，返回 `self`。

`await im.amark_private_read(friend_id)` — 异步标记。

`im.get_max_read_private_message_id(friend_id)` — 获取最大已读消息 ID，返回 `int`。

`await im.aget_max_read_private_message_id(friend_id)` — 异步获取。

`im.load_private_offline_message(min_id)` — 拉取 `min_id` 之后的私聊离线消息，返回 `List[Dict]`。

`await im.aload_private_offline_message(min_id)` — 异步拉取。

`im.get_private_message_history(friend_id, page=1, size=20)` — 分页获取私聊历史记录，返回 `List[Dict]`。

`await im.aget_private_message_history(friend_id, page=1, size=20)` — 异步获取。

`im.delete_private_messages(chat_id, message_ids)` — 删除指定私聊消息，`message_ids` 为 ID 列表，返回 `self`。

`await im.adelete_private_messages(chat_id, message_ids)` — 异步删除。

`im.delete_private_chat(chat_id)` — 删除与某用户的整个私聊会话，返回 `self`。

`await im.adelete_private_chat(chat_id)` — 异步删除。

---

## 群聊消息

所有发送方法需已登录，`at_users` 参数为 `List[int]`，`-1` 表示 @所有人，返回 `self`。

`im.send_group_text(group_id, text, at_users=None)` — 发送群聊文本。

`await im.asend_group_text(group_id, text, at_users=None)` — 异步发送。

`im.send_group_image(group_id, image_path, at_users=None)` — 上传并发送群聊图片。

`await im.asend_group_image(...)` — 异步发送。

`im.send_group_file(group_id, file_path, at_users=None)` — 上传并发送群聊文件。

`await im.asend_group_file(...)` — 异步发送。

`im.send_group_voice(group_id, voice_path, duration=3, at_users=None)` — 上传并发送群聊语音。

`await im.asend_group_voice(...)` — 异步发送。

`im.send_group_video(group_id, video_path, at_users=None)` — 上传并发送群聊视频。

`await im.asend_group_video(...)` — 异步发送。

`im.send_group_sticker(group_id, sticker_id, at_users=None)` — 发送群聊贴纸。

`await im.asend_group_sticker(...)` — 异步发送。

`im.send_group_raw(group_id, content, msg_type, at_users=None, receipt=False, quote_message_id=None)` — 发送原始群聊消息，完全控制内容，返回 `Dict`。

`await im.asend_group_raw(...)` — 异步发送。

`im.recall_group_message(message_id)` — 撤回群聊消息，返回 `self`。

`await im.arecall_group_message(message_id)` — 异步撤回。

`im.mark_group_read(group_id)` — 标记群聊消息为已读，返回 `self`。

`await im.amark_group_read(group_id)` — 异步标记。

`im.load_group_offline_message(min_id)` — 拉取群聊离线消息，返回 `List[Dict]`。

`await im.aload_group_offline_message(min_id)` — 异步拉取。

`im.get_group_message_readers(group_id, message_id)` — 获取某条群消息的已读用户 ID 列表，返回 `List[int]`。

`await im.aget_group_message_readers(group_id, message_id)` — 异步获取。

`im.get_group_message_history(group_id, page=1, size=20)` — 分页获取群聊历史记录，返回 `List[Dict]`。

`await im.aget_group_message_history(...)` — 异步获取。

`im.delete_group_messages(chat_id, message_ids)` — 删除指定群聊消息，返回 `self`。

`await im.adelete_group_messages(chat_id, message_ids)` — 异步删除。

`im.delete_group_chat(chat_id)` — 删除整个群聊会话，返回 `self`。

`await im.adelete_group_chat(chat_id)` — 异步删除。

---

## 系统消息

`im.load_system_offline_message(min_seq_no=0)` — 拉取序列号大于 `min_seq_no` 的系统离线消息，返回 `List[SystemMessage]`。

`await im.aload_system_offline_message(min_seq_no=0)` — 异步拉取。

`im.mark_system_read(max_seq_no)` — 标记序列号不大于 `max_seq_no` 的系统消息为已读，返回 `self`。

`await im.amark_system_read(max_seq_no)` — 异步标记。

`im.get_system_message_content(message_id)` — 获取系统消息详情，返回 `Dict`。

`await im.aget_system_message_content(message_id)` — 异步获取。

---

## 贴纸系统

`im.get_sticker_albums()` — 获取表情包专辑列表，返回 `List[StickerAlbum]`。

`await im.aget_sticker_albums()` — 异步获取。

`im.get_stickers(album_id)` — 获取指定专辑的贴纸列表，返回 `List[Sticker]`。

`await im.aget_stickers(album_id)` — 异步获取。

`im.search_stickers(name)` — 按关键词搜索贴纸，返回 `List[Sticker]`。

`await im.asearch_stickers(name)` — 异步搜索。

`im.get_custom_stickers()` — 获取当前用户自定义贴纸，返回 `List[Sticker]`。

`await im.aget_custom_stickers()` — 异步获取。

`im.add_custom_sticker(name, image_url, thumb_url, width=100, height=100)` — 添加自定义贴纸，返回 `self`。

`await im.aadd_custom_sticker(...)` — 异步添加。

`im.top_custom_sticker(sticker_id)` — 置顶自定义贴纸，返回 `self`。

`await im.atop_custom_sticker(sticker_id)` — 异步置顶。

`im.delete_custom_sticker(sticker_id)` — 删除自定义贴纸，返回 `self`。

`await im.adelete_custom_sticker(sticker_id)` — 异步删除。

---

## 消息监听

`im.on_message(handler)` — 注册消息处理器，`handler` 签名为 `(msg_data: Dict, is_group: bool) -> None`，支持同步和异步函数，返回 `self`。

`im.off_message(handler)` — 移除已注册的消息处理器，返回 `self`。

`@im.on_event("message")` — 装饰器方式注册 WebSocket 事件监听器，事件名可为 `"message"`、`"connected"`、`"disconnected"` 等。

`await im.listen()` — 阻塞式启动 WebSocket 监听，直到 `KeyboardInterrupt` 或协程取消。

`im.listen_sync()` — 同步阻塞式启动监听，内部调用 `asyncio.run`，直到 Ctrl+C 中断。

`await im.start_listening()` — 非阻塞启动监听，返回 `self`，可在启动后继续执行其他逻辑。

`await im.stop_listening()` — 停止 WebSocket 监听，返回 `self`。

---

## WebRTC 私聊通话（底层）

以下方法直接调用信令 API，适合手动管理通话流程。

`im.webrtc_setup(user_id, mode="video")` — 向对方发起通话建立请求，`mode` 为 `"voice"`/`"audio"`/`"video"`，返回 `Dict`。

`im.webrtc_accept(user_id, answer="")` — 接受来电，`answer` 为 SDP Answer 字符串或 JSON，返回 `Dict`。

`im.webrtc_reject(user_id)` — 拒绝来电，返回 `Dict`。

`im.webrtc_cancel(user_id)` — 主叫方取消通话，返回 `Dict`。

`im.webrtc_handup(user_id)` — 挂断通话，返回 `Dict`。

`im.webrtc_failed(user_id, reason="")` — 上报通话失败，返回 `Dict`。

`im.webrtc_offer(user_id, sdp)` — 发送 SDP Offer，返回 `Dict`。

`im.webrtc_answer(user_id, sdp)` — 发送 SDP Answer，返回 `Dict`。

`im.webrtc_send_candidate(user_id, candidate)` — 发送 ICE Candidate，返回 `Dict`。

`im.webrtc_heartbeat(user_id)` — 发送通话心跳保活，返回 `Dict`。

以上所有方法均有对应 `await im.awebrtc_*` 异步版本。

---

## WebRTC 群组通话（底层）

`im.webrtc_group_setup(group_id, user_infos=None)` — 发起群组通话，`user_infos` 为可选的被邀用户信息列表，返回 `Dict`。

`im.webrtc_group_accept(group_id)` — 接受群组通话，返回 `Dict`。

`im.webrtc_group_reject(group_id)` — 拒绝群组通话，返回 `Dict`。

`im.webrtc_group_join(group_id)` — 加入进行中的群组通话，返回 `Dict`。

`im.webrtc_group_invite(group_id, user_infos)` — 邀请成员加入通话，返回 `Dict`。

`im.webrtc_group_quit(group_id)` — 退出群组通话，返回 `Dict`。

`im.webrtc_group_cancel(group_id)` — 取消群组通话，返回 `Dict`。

`im.webrtc_group_failed(group_id, reason="")` — 上报群组通话失败，返回 `Dict`。

`im.webrtc_group_offer(group_id, user_id, offer)` — 向指定成员发送 SDP Offer，返回 `Dict`。

`im.webrtc_group_answer(group_id, user_id, answer)` — 向指定成员发送 SDP Answer，返回 `Dict`。

`im.webrtc_group_send_candidate(group_id, user_id, candidate)` — 向指定成员发送 ICE Candidate，返回 `Dict`。

`im.webrtc_group_device(group_id, is_camera=True, is_microphone=True, is_share_screen=False)` — 更新设备状态（摄像头/麦克风/屏幕共享），返回 `Dict`。

`im.webrtc_group_heartbeat(group_id)` — 群组通话心跳，返回 `Dict`。

`im.webrtc_group_info(group_id)` — 获取当前群组通话信息，返回 `Dict`。

以上所有方法均有对应 `await im.awebrtc_group_*` 异步版本。

---

## 高级通话接口

`im.create_call(user_id=None, group_id=None, mode=RTCMode.VIDEO, is_caller=True)` — 创建通话会话对象 `RTCCallSession`，`user_id` 和 `group_id` 二选一，同时指定或都不指定抛出 `ValidationError`，`mode` 支持 `RTCMode` 枚举或字符串 `"voice"`/`"video"`/`"audio"`。

`im.create_incoming_call(user_id=None, group_id=None, mode=RTCMode.VIDEO)` — 创建被叫方会话，等同于 `create_call(..., is_caller=False)`。

`im.active_calls` — 属性，返回当前活跃通话字典 `Dict[str, RTCCallSession]`，key 为 session_id。

---

## 验证码

`im.get_captcha_img()` — 获取图片验证码，返回 `CaptchaCode`（含 `id` 和 base64 图片）。

`await im.aget_captcha_img()` — 异步获取。

`im.verify_captcha_img(captcha_id, code)` — 验证图片验证码，返回 `bool`。

`await im.averify_captcha_img(captcha_id, code)` — 异步验证。

`im.send_sms_captcha(phone, captcha_id=None, captcha_code=None)` — 发送短信验证码，若平台要求图片验证则需提供 `captcha_id` 和 `captcha_code`，返回 `Dict`。

`await im.asend_sms_captcha(...)` — 异步发送。

`im.verify_sms_captcha(phone, code)` — 验证短信验证码，返回 `bool`。

`await im.averify_sms_captcha(phone, code)` — 异步验证。

`im.send_email_captcha(email)` — 发送邮件验证码，返回 `Dict`。

`await im.asend_email_captcha(email)` — 异步发送。

`im.verify_email_captcha(email, code)` — 验证邮件验证码，返回 `bool`。

`await im.averify_email_captcha(email, code)` — 异步验证。

---

## 投诉举报

`im.initiate_complaint(complaint_type, target_id, target_type, description, evidence=None, target_name=None)` — 发起投诉，`complaint_type` 为整数类型码，`target_type` 为 `"user"`/`"group"`/`"message"`，`evidence` 为证据图片 URL 列表，返回 `Dict`。

`await im.ainitiate_complaint(...)` — 异步发起。

---

## 系统配置

`im.get_system_config()` — 获取系统配置（注册方式、WebRTC 配置等），无需登录，返回 `SystemConfig`。

`await im.aget_system_config()` — 异步获取。

---

## 便捷函数（直接使用，无需 client）

`quick_login(username, password, base_url=None, debug=False)` — 快速创建并登录 `BoxIM` 实例，返回已登录实例。**注意：此函数不使用全局单例，多次调用会创建多个实例，建议生产环境使用 `initialize_im_client`。**

`await aquick_login(username, password, base_url=None, debug=False)` — 异步快速登录。

---

## 资源管理

`im.close()` — 同步关闭，释放 HTTP 连接。

`await im.aclose()` — 异步关闭，结束所有活跃通话、停止 WebSocket、释放全部资源。

同步上下文管理器 `with BoxIM() as im` 和异步上下文管理器 `async with BoxIM() as im` 在退出时自动调用对应关闭方法。

# BoxIM SDK 方法速查表

## 认证管理 (Authentication)
| 方法 | 说明 |
|------|------|
| `login()` / `alogin()` | 用户名密码登录 |
| `register()` / `aregister()` | 用户注册（支持用户名/手机/邮箱） |
| `refresh_token()` / `arefresh_token()` | 刷新访问令牌 |
| `modify_password()` / `amodify_password()` | 修改密码 |
| `reset_password()` / `areset_password()` | 重置密码（验证码） |
| `generate_qr_login()` / `agenerate_qr_login()` | 生成二维码登录信息 |
| `qr_login_wait()` / `aqr_login_wait()` | 轮询等待二维码扫码登录 |

## 用户信息 (User)
| 方法 | 说明 |
|------|------|
| `get_me()` / `aget_me()` | 获取当前用户信息 |
| `get_user()` / `aget_user()` | 根据ID获取用户信息 |
| `search_users()` / `asearch_users()` | 搜索用户 |
| `update_profile()` / `aupdate_profile()` | 更新个人资料 |
| `get_online_terminals()` / `aget_online_terminals()` | 获取用户在线终端 |

## 好友管理 (Friend)
| 方法 | 说明 |
|------|------|
| `get_friends()` / `aget_friends()` | 获取好友列表 |
| `get_friend_info()` / `aget_friend_info()` | 获取指定好友信息 |
| `add_friend()` / `aadd_friend()` | 发送好友请求 |
| `delete_friend()` / `adelete_friend()` | 删除好友 |
| `set_friend_dnd()` / `aset_friend_dnd()` | 设置免打扰 |
| `set_friend_top()` / `aset_friend_top()` | 设置置顶 |
| `update_friend_remark()` / `aupdate_friend_remark()` | 更新备注名 |

## 好友请求 (Friend Request)
| 方法 | 说明 |
|------|------|
| `get_friend_requests()` / `aget_friend_requests()` | 获取好友请求列表 |
| `accept_friend_request()` / `aaccept_friend_request()` | 接受好友请求 |
| `reject_friend_request()` / `areject_friend_request()` | 拒绝好友请求 |
| `recall_friend_request()` / `arecall_friend_request()` | 撤回好友请求 |

## 黑名单 (Blacklist)
| 方法 | 说明 |
|------|------|
| `add_to_blacklist()` / `aadd_to_blacklist()` | 加入黑名单 |
| `remove_from_blacklist()` / `aremove_from_blacklist()` | 移出黑名单 |
| `get_blacklist()` / `aget_blacklist()` | 获取黑名单列表 |

## 群组管理 (Group)
| 方法 | 说明 |
|------|------|
| `get_groups()` / `aget_groups()` | 获取群组列表 |
| `create_group()` / `acreate_group()` | 创建群组 |
| `get_group_info()` / `aget_group_info()` | 获取群组信息 |
| `modify_group()` / `amodify_group()` | 修改群组信息 |
| `delete_group()` / `adelete_group()` | 解散群组 |
| `quit_group()` / `aquit_group()` | 退出群组 |
| `join_group()` / `ajoin_group()` | 申请加入群组 |
| `get_group_members()` / `aget_group_members()` | 获取成员列表 |
| `get_group_online_members()` / `aget_group_online_members()` | 获取在线成员 |
| `invite_to_group()` / `ainvite_to_group()` | 邀请成员 |
| `remove_group_members()` / `aremove_group_members()` | 移出成员 |

## 群组设置 (Group Settings)
| 方法 | 说明 |
|------|------|
| `set_group_dnd()` / `aset_group_dnd()` | 免打扰设置 |
| `set_group_top()` / `aset_group_top()` | 置顶设置 |
| `set_group_muted()` / `aset_group_muted()` | 全员禁言 |
| `set_group_allow_invite()` / `aset_group_allow_invite()` | 允许邀请设置 |
| `set_group_allow_share_card()` / `aset_group_allow_share_card()` | 允许分享名片 |
| `set_group_member_muted()` / `aset_group_member_muted()` | 成员禁言 |
| `add_group_manager()` / `aadd_group_manager()` | 添加管理员 |
| `remove_group_manager()` / `aremove_group_manager()` | 移除管理员 |
| `set_group_top_message()` / `aset_group_top_message()` | 设置置顶消息 |
| `remove_group_top_message()` / `aremove_group_top_message()` | 移除置顶消息 |

## 私聊消息 (Private Message)
| 方法 | 说明 |
|------|------|
| `send_text()` / `asend_text()` | 发送文本 |
| `send_image()` / `asend_image()` | 发送图片 |
| `send_file()` / `asend_file()` | 发送文件 |
| `send_voice()` / `asend_voice()` | 发送语音 |
| `send_video()` / `asend_video()` | 发送视频 |
| `send_sticker()` / `asend_sticker()` | 发送贴纸 |
| `send_user_card()` / `asend_user_card()` | 发送个人名片 |
| `send_group_card()` / `asend_group_card()` | 发送群名片 |
| `recall_private_message()` / `arecall_private_message()` | 撤回消息 |
| `mark_private_read()` / `amark_private_read()` | 标记已读 |
| `load_private_offline_message()` / `aload_private_offline_message()` | 拉取离线消息 |
| `get_private_message_history()` / `aget_private_message_history()` | 获取历史记录 |
| `delete_private_messages()` / `adelete_private_messages()` | 删除消息 |
| `delete_private_chat()` / `adelete_private_chat()` | 删除会话 |

## 群聊消息 (Group Message)
| 方法 | 说明 |
|------|------|
| `send_group_text()` / `asend_group_text()` | 发送文本（支持@） |
| `send_group_image()` / `asend_group_image()` | 发送图片 |
| `send_group_file()` / `asend_group_file()` | 发送文件 |
| `send_group_voice()` / `asend_group_voice()` | 发送语音 |
| `send_group_video()` / `asend_group_video()` | 发送视频 |
| `send_group_sticker()` / `asend_group_sticker()` | 发送贴纸 |
| `recall_group_message()` / `arecall_group_message()` | 撤回消息 |
| `mark_group_read()` / `amark_group_read()` | 标记已读 |
| `load_group_offline_message()` / `aload_group_offline_message()` | 拉取离线消息 |
| `get_group_message_readers()` / `aget_group_message_readers()` | 获取已读用户 |
| `get_group_message_history()` / `aget_group_message_history()` | 获取历史记录 |

## 系统消息 (System Message)
| 方法 | 说明 |
|------|------|
| `load_system_offline_message()` / `aload_system_offline_message()` | 拉取系统离线消息 |
| `mark_system_read()` / `amark_system_read()` | 标记已读 |
| `get_system_message_content()` / `aget_system_message_content()` | 获取消息详情 |

## 贴纸系统 (Sticker)
| 方法 | 说明 |
|------|------|
| `get_sticker_albums()` / `aget_sticker_albums()` | 获取表情包列表 |
| `get_stickers()` / `aget_stickers()` | 获取贴纸列表 |
| `search_stickers()` / `asearch_stickers()` | 搜索贴纸 |
| `get_custom_stickers()` / `aget_custom_stickers()` | 获取自定义贴纸 |
| `add_custom_sticker()` / `aadd_custom_sticker()` | 添加自定义贴纸 |
| `top_custom_sticker()` / `atop_custom_sticker()` | 置顶自定义贴纸 |
| `delete_custom_sticker()` / `adelete_custom_sticker()` | 删除自定义贴纸 |

## WebRTC 私聊通话 (Private Call)
| 方法 | 说明 |
|------|------|
| `webrtc_setup()` / `awebrtc_setup()` | 发起通话建立 |
| `webrtc_accept()` / `awebrtc_accept()` | 接受通话 |
| `webrtc_reject()` / `awebrtc_reject()` | 拒绝通话 |
| `webrtc_cancel()` / `awebrtc_cancel()` | 取消通话 |
| `webrtc_handup()` / `awebrtc_handup()` | 挂断通话 |
| `webrtc_offer()` / `awebrtc_offer()` | 发送SDP Offer |
| `webrtc_answer()` / `awebrtc_answer()` | 发送SDP Answer |
| `webrtc_send_candidate()` / `awebrtc_send_candidate()` | 发送ICE Candidate |
| `webrtc_heartbeat()` / `awebrtc_heartbeat()` | 发送心跳 |

## WebRTC 群组通话 (Group Call)
| 方法 | 说明 |
|------|------|
| `webrtc_group_setup()` / `awebrtc_group_setup()` | 发起群组通话 |
| `webrtc_group_accept()` / `awebrtc_group_accept()` | 接受通话 |
| `webrtc_group_reject()` / `awebrtc_group_reject()` | 拒绝通话 |
| `webrtc_group_join()` / `awebrtc_group_join()` | 加入通话 |
| `webrtc_group_invite()` / `awebrtc_group_invite()` | 邀请成员 |
| `webrtc_group_quit()` / `awebrtc_group_quit()` | 退出通话 |
| `webrtc_group_cancel()` / `awebrtc_group_cancel()` | 取消通话 |
| `webrtc_group_offer()` / `awebrtc_group_offer()` | 发送Offer |
| `webrtc_group_answer()` / `awebrtc_group_answer()` | 发送Answer |
| `webrtc_group_send_candidate()` / `awebrtc_group_send_candidate()` | 发送Candidate |
| `webrtc_group_device()` / `awebrtc_group_device()` | 更新设备状态 |
| `webrtc_group_heartbeat()` / `awebrtc_group_heartbeat()` | 发送心跳 |
| `webrtc_group_info()` / `awebrtc_group_info()` | 获取通话信息 |

## 高级通话接口 (Advanced Call)
| 方法 | 说明 |
|------|------|
| `create_call()` | 创建通话会话（高级封装） |
| `create_incoming_call()` | 创建来电会话 |

## 验证码 (Captcha)
| 方法 | 说明 |
|------|------|
| `get_captcha_img()` / `aget_captcha_img()` | 获取图片验证码 |
| `verify_captcha_img()` / `averify_captcha_img()` | 验证图片验证码 |
| `send_sms_captcha()` / `asend_sms_captcha()` | 发送短信验证码 |
| `verify_sms_captcha()` / `averify_sms_captcha()` | 验证短信验证码 |
| `send_email_captcha()` / `asend_email_captcha()` | 发送邮件验证码 |
| `verify_email_captcha()` / `averify_email_captcha()` | 验证邮件验证码 |

## 投诉举报 (Complaint)
| 方法 | 说明 |
|------|------|
| `initiate_complaint()` / `ainitiate_complaint()` | 发起投诉举报 |

## 系统配置 (System Config)
| 方法 | 说明 |
|------|------|
| `get_system_config()` / `aget_system_config()` | 获取系统配置 |

## 消息监听 (Message Listener)
| 方法 | 说明 |
|------|------|
| `on_message()` | 注册消息处理器 |
| `off_message()` | 移除消息处理器 |
| `on_event()` | 事件装饰器 |
| `listen()` / `listen_sync()` | 开始监听（阻塞） |
| `start_listening()` / `stop_listening()` | 非阻塞启停监听 |

## 便捷函数 (Helpers)
| 函数 | 说明 |
|------|------|
| `quick_login()` | 同步快速登录 |
| `aquick_login()` | 异步快速登录 |

---

**属性访问**：`.me`、`.friends`、`.groups`、`.friend_requests`、`.config`、`.http`、`.ws`、`.uploader`、`.container`、`.token_store`、`.active_calls`
