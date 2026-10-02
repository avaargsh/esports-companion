import { request } from "../../api/client"

export type AnnouncementType = "NORMAL" | "SYSTEM"

export type PublicAnnouncement = {
  id: string
  title: string
  content: string
  audience: string
  noticeType: AnnouncementType
  publishedAt: string | null
}

export function listAnnouncements(limit = 3, noticeType: AnnouncementType = "NORMAL"): Promise<PublicAnnouncement[]> {
  return request<PublicAnnouncement[]>(`/announcements?limit=${limit}&notice_type=${noticeType}`)
}
