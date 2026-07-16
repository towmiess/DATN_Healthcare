import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Ban, ChevronDown, LockKeyhole, LockKeyholeOpen, RefreshCw, Search, ShieldCheck, Trash2, UserPlus, Users } from 'lucide-react';
import Swal from 'sweetalert2';
import { toast } from 'sonner';
import { fetcher } from '@/api/Fetcher';
import { getApiErrorMessage } from '@/utils/apiErrorMessage';
import './AdminUsers.scss';

type UserStatus = 'ACTIVE' | 'BLOCKED' | 'INACTIVE';
type FilterStatus = 'ALL' | 'ACTIVE' | 'BLOCKED';

type AdminUser = {
  id: number;
  fullName: string;
  email: string;
  phoneNumber: string;
  avatar?: string | null;
  status: UserStatus;
  roles?: string[];
  createdAt?: string;
  updatedAt?: string;
};

type UserSummary = {
  totalUsers: number;
  activeUsers: number;
  blockedUsers: number;
  recentUsers: number;
};

const statusLabels: Record<UserStatus, string> = {
  ACTIVE: 'Hoạt động',
  BLOCKED: 'Tạm khóa',
  INACTIVE: 'Tạm khóa',
};

const nextStatus: Record<UserStatus, 'ACTIVE' | 'BLOCKED'> = {
  ACTIVE: 'BLOCKED',
  BLOCKED: 'ACTIVE',
  INACTIVE: 'ACTIVE',
};

const statusOptions: Array<{ value: FilterStatus; label: string }> = [
  { value: 'ALL', label: 'Tất cả trạng thái' },
  { value: 'ACTIVE', label: 'Hoạt động' },
  { value: 'BLOCKED', label: 'Tạm khóa' },
];

const formatDate = (value?: string) => {
  if (!value) return 'Chưa có';
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
};

const getInitials = (name?: string) => {
  const parts = (name || 'User').trim().split(/\s+/);
  return parts
    .slice(-2)
    .map((part) => part[0])
    .join('')
    .toUpperCase();
};

const AdminUsers: React.FC = () => {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [summary, setSummary] = useState<UserSummary>({
    totalUsers: 0,
    activeUsers: 0,
    blockedUsers: 0,
    recentUsers: 0,
  });
  const [keyword, setKeyword] = useState('');
  const [status, setStatus] = useState<FilterStatus>('ALL');
  const [isStatusMenuOpen, setIsStatusMenuOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [actionUserId, setActionUserId] = useState<number | null>(null);
  const statusMenuRef = useRef<HTMLDivElement | null>(null);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const trimmedKeyword = keyword.trim();
      const params = {
        size: 100,
        ...(status !== 'ALL' ? { status } : {}),
        ...(trimmedKeyword
          ? {
              fullName: trimmedKeyword,
              email: trimmedKeyword,
              phoneNumber: trimmedKeyword,
            }
          : {}),
      };

      const [userList, userSummary] = await Promise.all([
        fetcher<AdminUser[]>({
          url: '/users',
          method: 'GET',
          params,
          unwrapData: true,
        }),
        fetcher<UserSummary>({
          url: '/users/summary',
          method: 'GET',
          unwrapData: true,
        }),
      ]);

      setUsers(userList);
      setSummary(userSummary);
    } catch (error) {
      console.error('Load users error:', error);
      toast.error(
        getApiErrorMessage(error, 'Không tải được danh sách người dùng.', {
          forbiddenMessage: 'Bạn không có quyền truy cập danh sách người dùng.',
          unauthorizedMessage: 'Phiên đăng nhập không hợp lệ. Vui lòng đăng nhập lại.',
        })
      );
    } finally {
      setLoading(false);
    }
  }, [keyword, status]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (!statusMenuRef.current?.contains(event.target as Node)) {
        setIsStatusMenuOpen(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsStatusMenuOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, []);

  const selectedStatusLabel = useMemo(
    () => statusOptions.find((option) => option.value === status)?.label ?? statusOptions[0].label,
    [status]
  );

  const summaryCards = useMemo(
    () => [
      { label: 'Tổng người dùng', value: summary.totalUsers, icon: <Users size={20} />, tone: 'blue' },
      { label: 'Đang hoạt động', value: summary.activeUsers, icon: <ShieldCheck size={20} />, tone: 'green' },
      { label: 'Tạm khóa', value: summary.blockedUsers, icon: <Ban size={20} />, tone: 'rose' },
      { label: 'Người dùng mới gần đây', value: summary.recentUsers, icon: <UserPlus size={20} />, tone: 'amber' },
    ],
    [summary]
  );

  const handleToggleStatus = async (user: AdminUser) => {
    const updatedStatus = nextStatus[user.status] ?? 'ACTIVE';
    const isBlocking = updatedStatus === 'BLOCKED';
    const confirmResult = await Swal.fire({
      title: isBlocking ? 'Tạm khóa người dùng?' : 'Mở khóa người dùng?',
      text: isBlocking
        ? `Người dùng ${user.email} sẽ không thể đăng nhập cho đến khi được mở khóa.`
        : `Người dùng ${user.email} sẽ có thể đăng nhập lại.`,
      icon: 'warning',
      showCancelButton: true,
      confirmButtonText: isBlocking ? 'Tạm khóa' : 'Mở khóa',
      cancelButtonText: 'Hủy',
      reverseButtons: true,
      confirmButtonColor: isBlocking ? '#ef4444' : '#00a98a',
      cancelButtonColor: '#64748b',
    });

    if (!confirmResult.isConfirmed) {
      return;
    }

    setActionUserId(user.id);
    try {
      const updatedUser = await fetcher<AdminUser>({
        url: `/users/${user.id}/status`,
        method: 'PATCH',
        data: { status: updatedStatus },
        unwrapData: true,
      });

      setUsers((prev) => prev.map((item) => (item.id === updatedUser.id ? updatedUser : item)));
      await loadUsers();
      await Swal.fire({
        title: isBlocking ? 'Đã tạm khóa người dùng này' : 'Đã mở khóa người dùng này',
        text: `${user.fullName} (${user.email})`,
        icon: 'success',
        confirmButtonText: 'Đã hiểu',
        confirmButtonColor: '#00a98a',
      });
    } catch (error) {
      console.error('Update user status error:', error);
      toast.error(
        getApiErrorMessage(error, 'Không thể cập nhật trạng thái người dùng.', {
          forbiddenMessage: 'Bạn không có quyền thay đổi trạng thái người dùng.',
          unauthorizedMessage: 'Phiên đăng nhập không hợp lệ. Vui lòng đăng nhập lại.',
        })
      );
      await Swal.fire({
        title: 'Không thể cập nhật trạng thái',
        text: 'Vui lòng thử lại sau.',
        icon: 'error',
        confirmButtonText: 'Đóng',
        confirmButtonColor: '#ef4444',
      });
    } finally {
      setActionUserId(null);
    }
  };

  const handleDeleteUser = async (user: AdminUser) => {
    const confirmResult = await Swal.fire({
      title: 'Bạn có muốn xóa người dùng này?',
      text: `Người dùng ${user.email} sẽ bị xóa khỏi danh sách quản lý.`,
      icon: 'warning',
      showCancelButton: true,
      confirmButtonText: 'Xóa',
      cancelButtonText: 'Hủy',
      reverseButtons: true,
      confirmButtonColor: '#ef4444',
      cancelButtonColor: '#64748b',
    });

    if (!confirmResult.isConfirmed) {
      return;
    }

    setActionUserId(user.id);
    try {
      await fetcher<void>({
        url: `/users/${user.id}`,
        method: 'DELETE',
        unwrapData: true,
      });

      setUsers((prev) => prev.filter((item) => item.id !== user.id));
      await loadUsers();
      await Swal.fire({
        title: 'Đã xóa người dùng này',
        text: `${user.fullName} (${user.email})`,
        icon: 'success',
        confirmButtonText: 'Đã hiểu',
        confirmButtonColor: '#00a98a',
      });
    } catch (error) {
      console.error('Delete user error:', error);
      toast.error(
        getApiErrorMessage(error, 'Không thể xóa người dùng.', {
          forbiddenMessage: 'Bạn không có quyền xóa người dùng.',
          unauthorizedMessage: 'Phiên đăng nhập không hợp lệ. Vui lòng đăng nhập lại.',
        })
      );
      await Swal.fire({
        title: 'Không thể xóa người dùng',
        text: 'Vui lòng thử lại sau.',
        icon: 'error',
        confirmButtonText: 'Đóng',
        confirmButtonColor: '#ef4444',
      });
    } finally {
      setActionUserId(null);
    }
  };

  return (
    <section className="admin-page admin-users">
      <div className="admin-page__head">
        <div>
          <h1 className="admin-page__title">Quản lý tài khoản hệ thống</h1>
          <p className="admin-page__sub">
            Tìm kiếm bằng email, họ tên hoặc số điện thoại. Email là định danh chính của người dùng trong hệ thống.
          </p>
        </div>

        <button type="button" className="admin-users__refresh" onClick={loadUsers} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'admin-users__spin' : ''} />
          Làm mới
        </button>
      </div>

      <div className="admin-users__summary">
        {summaryCards.map((card) => (
          <article className={`admin-users__summary-card admin-users__summary-card--${card.tone}`} key={card.label}>
            <span>{card.icon}</span>
            <div>
              <p>{card.label}</p>
              <strong>{card.value}</strong>
            </div>
          </article>
        ))}
      </div>

      <div className="admin-panel admin-users__panel">
        <div className="admin-users__toolbar">
          <label className="admin-users__search">
            <Search size={17} />
            <input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="Tìm theo email, họ tên hoặc số điện thoại..."
            />
          </label>

          <div className="admin-users__filter-wrap" ref={statusMenuRef}>
            <button
              type="button"
              className={`admin-users__filter ${isStatusMenuOpen ? 'admin-users__filter--open' : ''}`}
              onClick={() => setIsStatusMenuOpen((prev) => !prev)}
              aria-haspopup="listbox"
              aria-expanded={isStatusMenuOpen}
              aria-label="Lọc trạng thái"
            >
              <span>{selectedStatusLabel}</span>
              <ChevronDown size={16} />
            </button>

            {isStatusMenuOpen ? (
              <div className="admin-users__filter-menu" role="listbox" aria-label="Danh sách trạng thái">
                {statusOptions.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    role="option"
                    className={`admin-users__filter-option ${status === option.value ? 'admin-users__filter-option--active' : ''}`}
                    aria-selected={status === option.value}
                    onClick={() => {
                      setStatus(option.value);
                      setIsStatusMenuOpen(false);
                    }}
                  >
                    <span>{option.label}</span>
                    {status === option.value ? <span className="admin-users__filter-dot" /> : null}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        </div>

        <div className="admin-users__table-wrap">
          <table className="admin-table admin-users__table">
            <thead>
              <tr>
                <th>Người dùng</th>
                <th>Email</th>
                <th>Số điện thoại</th>
                <th>Vai trò</th>
                <th>Trạng thái</th>
                <th>Ngày tạo</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>
                    <div className="admin-users__person">
                      {user.avatar ? (
                        <img src={user.avatar} alt={user.fullName} />
                      ) : (
                        <span>{getInitials(user.fullName)}</span>
                      )}
                      <strong>{user.fullName}</strong>
                    </div>
                  </td>
                  <td>{user.email}</td>
                  <td>{user.phoneNumber}</td>
                  <td>
                    <div className="admin-users__roles">
                      {(user.roles?.length ? user.roles : ['USER']).map((role) => (
                        <span key={role}>{role}</span>
                      ))}
                    </div>
                  </td>
                  <td>
                    <span className={`admin-users__status admin-users__status--${user.status.toLowerCase()}`}>
                      {statusLabels[user.status] ?? user.status}
                    </span>
                  </td>
                  <td>{formatDate(user.createdAt)}</td>
                  <td>
                    <div className="admin-users__actions">
                      <button
                        type="button"
                        onClick={() => handleToggleStatus(user)}
                        disabled={actionUserId === user.id}
                      >
                        {user.status === 'ACTIVE' ? <LockKeyhole size={15} /> : <LockKeyholeOpen size={15} />}
                      </button>
                      <button
                        type="button"
                        className="admin-users__danger"
                        onClick={() => handleDeleteUser(user)}
                        disabled={actionUserId === user.id}
                        aria-label={`Xóa ${user.email}`}
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}

              {!loading && users.length === 0 && (
                <tr>
                  <td colSpan={7}>
                    <div className="admin-users__empty">
                      <Users size={34} />
                      <strong>Chưa có người dùng phù hợp</strong>
                      <span>Thử đổi từ khóa email hoặc bộ lọc trạng thái.</span>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {loading && <div className="admin-users__loading">Đang tải danh sách người dùng...</div>}
      </div>
    </section>
  );
};

export default AdminUsers;
